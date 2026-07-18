"""Seed: creates one agent + one employee user (idempotent).

KB articles live in kb/*.md and are indexed into the in-memory vector store
at API boot, so there is nothing to load into Postgres for them.

Run:  python seed.py
"""
from app.db import Base, SessionLocal, engine
from app.models import Role, User
from app.security import hash_password

USERS = [
    ("agent@quickdesk.local", "agentpass123", Role.agent),
    ("employee@quickdesk.local", "employeepass123", Role.employee),
]


def main():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        for email, password, role in USERS:
            if db.query(User).filter_by(email=email).first():
                print(f"exists: {email}")
                continue
            db.add(User(email=email, password_hash=hash_password(password), role=role))
            print(f"created: {email} / {password} ({role.value})")
        db.commit()
    finally:
        db.close()
    print("Seed done. KB articles are indexed automatically when the API starts.")


if __name__ == "__main__":
    main()
