"""Critical-path tests: auth, role enforcement, RAG fallback, ticket lifecycle.

Runs on in-memory SQLite with the mock LLM — no Postgres, no API key needed.
    cd backend && pytest
"""
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import ai
from app.config import settings
from app.db import Base, get_db
from app.main import app

settings.groq_api_key = ""  # force mock LLM path

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


@asynccontextmanager
async def _null_lifespan(_app):
    yield  # skip Postgres create_all + vector store build


app.router.lifespan_context = _null_lifespan


def _override_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db
client = TestClient(app)


def _register(email, role):
    r = client.post("/auth/register", json={"email": email, "password": "secretpass1!", "role": role})
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


EMPLOYEE = _register("emp@test.quickdesk.io", "employee")
EMPLOYEE2 = _register("emp2@test.quickdesk.io", "employee")
AGENT = _register("agent@test.quickdesk.io", "agent")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_and_password_hashing():
    ok = client.post("/auth/login", json={"email": "emp@test.quickdesk.io", "password": "secretpass1!"})
    assert ok.status_code == 200
    bad = client.post("/auth/login", json={"email": "emp@test.quickdesk.io", "password": "wrongwrong"})
    assert bad.status_code == 401
    # password stored as bcrypt hash, never plaintext
    from app.models import User
    db = TestSession()
    user = db.query(User).filter_by(email="emp@test.quickdesk.io").one()
    db.close()
    assert user.password_hash.startswith("$2")
    assert "secretpass1!" not in user.password_hash


def test_employee_blocked_from_agent_routes():
    for method, path in [("get", "/metrics"), ("patch", "/tickets/1/classification"),
                         ("post", "/tickets/1/draft-reply"), ("get", "/tickets/1/audit-log")]:
        r = getattr(client, method)(path, headers=_auth(EMPLOYEE), **({"json": {}} if method in ("patch", "post") else {}))
        assert r.status_code == 403, f"{path} returned {r.status_code}"


def test_unauthenticated_gets_401():
    assert client.get("/tickets").status_code == 401


def test_ticket_lifecycle_with_ai_suggestion_override_and_reply():
    # employee raises a ticket -> mock LLM classifies it as IT (mentions VPN)
    r = client.post("/tickets", json={"title": "VPN not connecting", "description": "urgent, cannot work"},
                    headers=_auth(EMPLOYEE))
    assert r.status_code == 201
    t = r.json()
    assert t["ai_category"] == "IT" and t["ai_priority"] == "High" and t["status"] == "open"

    # other employee cannot see it (404, not 403 — no information leak)
    assert client.get(f"/tickets/{t['id']}", headers=_auth(EMPLOYEE2)).status_code == 404
    # agents cannot create tickets
    assert client.post("/tickets", json={"title": "abc", "description": "def"}, headers=_auth(AGENT)).status_code == 403

    # agent overrides the category -> audit log entry
    r = client.patch(f"/tickets/{t['id']}/classification", json={"category": "Admin"}, headers=_auth(AGENT))
    assert r.status_code == 200 and r.json()["category"] == "Admin"
    log = client.get(f"/tickets/{t['id']}/audit-log", headers=_auth(AGENT)).json()
    assert len(log) == 1 and log[0]["old_value"] == "IT" and log[0]["new_value"] == "Admin"

    # agent sends a reply -> ticket resolved, both drafts stored
    r = client.post(f"/tickets/{t['id']}/reply",
                    json={"ai_draft": "draft text", "final_reply": "edited text", "citations": ["VPN Setup Guide"]},
                    headers=_auth(AGENT))
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    assert r.json()["reply"]["ai_draft"] == "draft text"
    # second reply rejected
    assert client.post(f"/tickets/{t['id']}/reply",
                       json={"ai_draft": "", "final_reply": "again"}, headers=_auth(AGENT)).status_code == 409


class _FakeStore:
    """Similarity scores below threshold -> RAG must refuse, not hallucinate."""
    def similarity_search_with_score(self, query, k):
        return []


def test_rag_refuses_when_no_relevant_article(monkeypatch):
    monkeypatch.setattr(ai, "_vector_store", _FakeStore())
    result = ai.draft_reply("Buy me a pony", "completely unrelated to any KB article")
    assert result["citations"] == []
    assert "don't have enough" in result["draft"]
