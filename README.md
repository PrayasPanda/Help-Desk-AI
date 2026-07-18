# QuickDesk — AI-Assisted Helpdesk

An internal helpdesk where employees raise support tickets and support agents resolve them faster with AI help: an LLM suggests a category and priority on submission, and drafts a reply grounded (via RAG over a small markdown knowledge base) that the agent reviews, edits, and sends. The AI never replies on its own — every classification is overridable (and audited) and every reply passes through a human agent.

**Stack:** FastAPI + SQLAlchemy + Postgres · React (Vite, TypeScript) · LangChain + Groq (`llama-3.3-70b-versatile`) · FastEmbed embeddings · SSE for real-time.

## How to run locally

Prereqs: Python 3.11+, Node 18+, Docker Desktop.

```bash
# 1. Database
docker compose up -d          # Postgres 16 on localhost:5432

# 2. Environment
cp .env.example .env          # then put your Groq key in GROQ_API_KEY
                              # (leave empty to run against the built-in mock LLM)

# 3. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows   (source .venv/bin/activate on mac/linux)
pip install -r requirements.txt
python seed.py                # creates demo users (idempotent)
uvicorn app.main:app --reload # http://localhost:8000  (indexes kb/*.md on boot)

# 4. Frontend (new terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

Seeded users: `agent@quickdesk.io / agentpass123` and `employee@quickdesk.io / employeepass123`.

First boot downloads the FastEmbed embedding model (~130 MB, one-time). Tests: `cd backend && pytest` (runs on SQLite + mock LLM — no DB or API key needed).

## Architecture

```
┌───────────────┐   HTTP (JSON, JWT bearer)   ┌──────────────────────────┐
│ React (Vite)  │ ──────────────────────────► │ FastAPI                  │
│  employee UI  │                             │  /auth   bcrypt + JWT    │
│  agent UI     │ ◄────────────────────────── │  /tickets CRUD+override  │──► Postgres
│               │   SSE /events (?token=)     │  /metrics SQL aggregates │    (users, tickets,
└───────────────┘                             │  ai.py                   │     replies, audit log)
                                              │   ├ classify() ──► Groq  │
                                              │   └ draft_reply()        │
                                              │      ▲ retrieval          │
                                              │  InMemoryVectorStore      │
                                              │   (FastEmbed, kb/*.md,    │
                                              │    rebuilt on boot)       │
                                              └──────────────────────────┘
```

- One SSE broker in-process: `ticket:created` → all connected agents; `ticket:resolved` → the ticket's employee + agents.
- KB articles live as `kb/*.md` files, chunked and embedded into an in-memory vector store at startup (no persistence needed at this scale).
- `category`/`priority` on a ticket are the *current* values; `ai_category`/`ai_priority` preserve the original suggestion forever — that's what makes the override-rate metric honest.

## API endpoints

| Method | Path | Purpose | Auth |
|---|---|---|---|
| POST | `/auth/register` | Create user, returns JWT | Public |
| POST | `/auth/login` | Issue JWT | Public |
| GET | `/auth/me` | Current user | Any JWT |
| GET | `/tickets` | List (own if employee, all if agent) + `?status=&category=&priority=&q=&page=&limit=` | Any JWT |
| POST | `/tickets` | Create ticket → LLM suggests category/priority/confidence | Employee |
| GET | `/tickets/:id` | Detail incl. reply + audit log | Owner or agent |
| PATCH | `/tickets/:id/classification` | Override category/priority (writes audit log) | Agent |
| POST | `/tickets/:id/draft-reply` | Generate RAG draft + citations (stateless, regenerable) | Agent |
| POST | `/tickets/:id/reply` | Send final reply → resolves ticket, stores AI draft + final | Agent |
| GET | `/tickets/:id/audit-log` | Override history | Agent |
| GET | `/metrics` | Status/category counts, median resolution, override rate | Agent |
| GET | `/events` | SSE stream (`?token=` because EventSource can't set headers) | Any JWT |
| GET | `/health` | Liveness + which LLM mode is active | Public |

## Decisions and tradeoffs

**a) React (Vite) over Next.js.** This is an internal tool that lives entirely behind a login — there is no SEO, no public pages, and no server-rendered content to gain from Next. A Vite SPA is one less runtime, one less deployment concern, and keeps the backend as the single API authority. If this grew public marketing pages or needed per-request server rendering, Next would earn its place.

**b) RAG pipeline.** `kb/*.md` → `RecursiveCharacterTextSplitter` (chunk 500 chars, overlap 50 — the articles are 100–300 words, so most become 1–2 chunks and headers stay attached to their body) → FastEmbed `BAAI/bge-small-en-v1.5` embeddings (local, free, no API dependency for retrieval) → LangChain `InMemoryVectorStore`, rebuilt on boot (7 tiny articles; persistence would be pure ceremony) → top-k=3 retrieval with a 0.55 cosine-similarity floor. If nothing clears the floor, the endpoint returns a fixed "no relevant KB article" draft with zero citations *before* the LLM is ever called — the model can't hallucinate about context it never sees. The prompt hard-constrains the LLM to the provided context and demands JSON `{reply, citations}`; returned citations are filtered against the set of articles actually retrieved, so the model can't cite things it wasn't shown.

**c) Invalid LLM category.** The category/priority strings from the model are parsed against the Python enums (which are also Postgres enums — the DB rejects garbage even if app code regressed). On mismatch: category falls back to `Other`, priority to `Medium`, and a warning is logged with the raw value. On any LLM/API failure, a deterministic keyword classifier takes over so ticket creation never fails because the AI did.

**d) JWT in localStorage.** Chosen for simplicity: no CSRF surface (nothing is sent automatically), trivial to attach to both `fetch` and the SSE URL. The tradeoff is XSS exposure — an injected script could read the token. Accepted here because the app renders no user-supplied HTML (React escapes by default) and it's an internal tool; in production I'd move to an httpOnly cookie + CSRF token and add a CSP.

**e) Backend role enforcement.** Every protected route declares a FastAPI dependency — `get_current_user` (validates the JWT signature/expiry) or `require_agent` (403 unless `role == agent`). Authorization is in route signatures, not scattered `if`s, so a route can't forget it silently. URL-guessing gets an employee nothing: agent routes 403 regardless of what the frontend hides, and fetching someone else's ticket returns **404, not 403**, so an employee probing IDs can't even learn which tickets exist. Verified by tests hitting agent routes with an employee token.

**f) SSE over Socket.io/WebSockets.** Both real-time flows are strictly server→client (new ticket → agents, resolved → employee), so a bidirectional channel buys nothing. SSE is plain HTTP — no extra protocol, no client library, and the browser's `EventSource` **reconnects automatically**. Failure mode: if the connection drops mid-session, the UI shows a "reconnecting…" badge; on every (re)open the client refetches the ticket list, so events missed while offline are recovered. Worst case is a stale list for a few seconds, never lost data — the DB is always the source of truth.

**g) Worst failure mode today.** Ticket creation calls the LLM synchronously, so a slow Groq response makes the employee's submit hang for seconds (and the in-process SSE broker means real-time only works with a single backend process). Fix: create the ticket immediately with `category=NULL`, classify in a background task, and push the suggestion over the existing SSE channel when ready; move the broker to Redis pub/sub the day this needs a second process.

**h) Where AI tools helped/misled.** Helped most: scaffolding the repetitive layers (Pydantic schemas mirroring models, the TS types mirroring those, CSS) and writing the KB articles. Misled: an early suggestion to authenticate SSE with an `Authorization` header — `EventSource` can't set headers, which forced the `?token=` query-param design; and LangChain API churn (several suggested imports were from deprecated module paths and had to be checked against current docs). All auth, role-guard, and RAG-threshold logic was reviewed line-by-line — those are exactly the paths the brief says get tested.

## What I would do with more time

- Async LLM classification (see g) and a Redis-backed SSE broker for multi-process deploys.
- Alembic migrations instead of `create_all` on boot.
- Refresh tokens + httpOnly cookie auth.
- Rate limiting on `/auth/login` and ticket submission.
- Full docker-compose including backend + frontend, not just Postgres.

## Known issues / limitations

- Single backend process assumed (in-memory SSE broker + vector store).
- Schema changes require dropping the DB (no migrations yet).
- `GET /kb` transparency endpoint not implemented; citations show article titles only.
- The mock LLM (no `GROQ_API_KEY`) is keyword-based — fine for exercising code paths, not for classification quality.

## Disclosures

- No boilerplate/starter template used; the repo was built from scratch.
- LLM provider: **Groq** free tier (`llama-3.3-70b-versatile`). With no key configured, a deterministic mock covers the same code paths (`/health` reports which mode is active).
- AI coding tools (Claude) were used throughout development; see tradeoff (h).
