# DocuMind — Project Context

> This document is the single source of truth for the DocuMind project.
> Paste this into every new Claude conversation to maintain consistency.
> Update it as new decisions are made.

---

## What is DocuMind

A multi-tenant RAG (Retrieval-Augmented Generation) system where users create
projects, upload documents to those projects, and query an LLM for answers
grounded in their documents. Every user's data is fully isolated. Built to
work with both cloud LLMs (Claude, OpenAI) and local LLMs (Ollama) so it can
be used as a personal tool or a production SaaS product. Chat is
session-based (`chat_sessions` → many `query_history` messages), not a single
flat log per project.

---

## Tech Stack

| Layer | Choice | Status |
|---|---|---|
| Backend | FastAPI + asyncpg | Installed, in use |
| ORM | SQLAlchemy (async) | Installed, in use |
| Database | PostgreSQL + pgvector (self-hosted Supabase) | Schema + migrations exist |
| Auth | PyJWT + pwdlib (argon2) | Implemented (register/login) |
| File Storage | Supabase Storage | Client wired up (`app/core/supabase_client.py`), no upload code yet |
| Migrations | Alembic | 3 migrations applied (initial, chat_session, billing) |
| Config | pydantic-settings | Implemented (`app/core/config.py`) |
| Embeddings | Open source, 768 dims | Chosen (`Chunk.EMBEDDING_DIM = 768`), no embedding call written yet |
| LLM | Claude / OpenAI / Ollama | Planned — no SDK installed, no `rag/` code yet |
| Agent Orchestration | LangGraph + Pydantic AI | **New decision (see README), not yet reflected in code or dependencies** |
| Payments | Stripe / SSLCommerz behind `PaymentGateway` interface | Interface + stubs only, both raise `NotImplementedError` |

---

## Current Implementation Status

What actually works end-to-end today:
- User registration and login (`/auth/register`, `/auth/login`) — JWT access tokens.
- Project CRUD: list (with document counts), create, get-one (with documents +
  chat sessions), delete (`/projects`).

Everything else — document upload/ingestion, RAG query, chat messages,
memory/insights generation, billing, usage tracking, BYOK API keys — has a
DB schema and (for billing) an interface skeleton, but **no working route or
business logic**. See "Files Written So Far" below for the file-by-file
breakdown.

---

## Folder Structure (actual)

```
DocuMind/
├── app/
│   ├── api/
│   │   ├── auth.py          # ✅ register, login
│   │   └── projects.py      # ✅ list, create, get, delete
│   ├── billing/
│   │   └── payment_gateway.py  # ✅ abstract interface + Stripe/SSLCommerz stubs (NotImplementedError)
│   ├── core/
│   │   ├── config.py            # ✅ pydantic-settings, env vars
│   │   ├── security.py          # ✅ JWT create/verify, password hashing, get_current_user
│   │   └── supabase_client.py   # ✅ Supabase client instance (service role key)
│   ├── db/
│   │   ├── database.py      # ✅ engine, session factory, get_db, init_db, close_db
│   │   ├── models.py        # ✅ User, Project, Document, Chunk, ChatSession, QueryHistory,
│   │   │                    #    ProjectMemory, ProjectInsights
│   │   ├── billing.py       # ✅ Plan, Subscription, UserApiKey, TokenUsageLog
│   │   ├── drop_downs.py    # ✅ enums: UserRole, UserPlan, SubscriptionStatus,
│   │   │                    #    BillingInterval, LLMProvider, DocumentStatus
│   │   ├── model_utils.py   # ✅ uuid_pk(), now_utc() shared column helpers
│   │   └── __init__.py      # ✅ re-exports all models
│   └── schemas/
│       ├── user.py          # ✅ UserRegister, UserRegisterResponse, Token, TokenData
│       └── projects.py      # ✅ Project*, Document*, ChatSession*, ChatMessageOut
├── alembic/
│   └── versions/
│       ├── 97a4f43a8f8c_initial_migration.py
│       ├── ff1cd28ed64b_chat_session.py
│       └── 598ae27864c2_billing.py
├── guide/
│   ├── PROJECT_CONTEXT.md
│   ├── alembic_commands.md
│   └── SUPABASE_SELFHOST_GUIDE.md
├── main.py               # app factory — mounts auth + projects only
├── .env / .env.example
└── pyproject.toml
```

**Not yet created** (still just planned): `app/core/deps.py`,
`app/api/documents.py`, `app/api/query.py`, `app/api/billing.py`,
`app/api/usage.py`, `app/api/api_keys.py`, `app/rag/*`, `app/storage/*`,
`Dockerfile`, `docker-compose.yml`, frontend.

---

## Database Schema

### Tables overview

| Table | Purpose | Defined in |
|---|---|---|
| users | One row per registered user, has `role` (admin/user) | `app/db/models.py` |
| projects | Belongs to a user, top-level container | `app/db/models.py` |
| documents | Each uploaded file with ingestion status | `app/db/models.py` |
| chunks | Text chunks + vector embeddings (pgvector) | `app/db/models.py` |
| chat_sessions | A conversation thread within a project | `app/db/models.py` |
| query_history | Every Q&A pair; optionally linked to a chat_session | `app/db/models.py` |
| project_memory | Long-term compressed memory per project | `app/db/models.py` |
| project_insights | Living blog-style summary post per project | `app/db/models.py` |
| plans | Subscription tier catalogue (Free, Pro, Team) | `app/db/billing.py` |
| subscriptions | One row per user — current plan + gateway billing state | `app/db/billing.py` |
| user_api_keys | Encrypted LLM provider keys per user (BYOK) | `app/db/billing.py` |
| token_usage_log | Per-call token counts + cost, drives usage dashboard | `app/db/billing.py` |

Billing tables intentionally live in a separate `app/db/billing.py`, not in
`models.py` — keeps subscription/quota logic decoupled from the core
RAG domain model file.

### Key schema decisions (do not change without good reason)

**Isolation pattern** — `user_id` is denormalized directly onto `chunks` and
`documents` even though it could be derived via join through `projects`. This
is intentional — every vector search filters by `project_id AND user_id` so
ownership checks need zero joins on the hot query path.

**pgvector** — `chunks.embedding` is `vector(768)`, defined as
`Chunk.EMBEDDING_DIM` (a class constant, **not** an env var — despite what
`.env.example`/README historically implied). Change that constant if
switching embedding models, and regenerate the Alembic migration.

**Chat sessions are implemented, not deferred** — `chat_sessions` is a real
table (`app/db/models.py`, migration `ff1cd28ed64b_chat_session.py`).
`query_history.session_id` is a nullable FK to `chat_sessions.id`
(`ON DELETE SET NULL`), not just a reserved column. A query can exist
without a session (legacy/ungrouped), but new chat UI should create a
`ChatSession` first and attach messages to it.

**Lean sources** — `query_history.sources` stores only
`{doc_id, filename, score}` per source. No chunk text. Chunk text is
re-fetched by doc_id if ever needed. This keeps rows small.

**Retention** — `query_history.expires_at` is intended to be set to
`asked_at + 90 days` on insert, with a `pg_cron` job doing
`DELETE FROM query_history WHERE expires_at < now();`. Column exists;
nothing sets it yet since `/query` isn't implemented.

**`unique=True` on memory/insights** — `project_memory.project_id` and
`project_insights.project_id` are both unique — exactly one row per project.
Upsert on these tables, never insert.

**`lazy="noload"`** — All SQLAlchemy relationships use `lazy="noload"`.
Never rely on implicit relationship loading. Always explicit join or
selectinload when you need related data. Required for async SQLAlchemy.

**`expire_on_commit=False`** — Set on the session factory. Required in async
SQLAlchemy — without it, accessing any attribute after a commit raises an
error due to failed lazy load.

**Billing isolation** — `subscriptions` is a separate table from `users`,
not columns on the `users` row. This keeps upserts clean — the gateway
webhook handler touches only `subscriptions`, never `users`.

**`ON DELETE RESTRICT` on plan_id** — `subscriptions.plan_id` uses RESTRICT,
not CASCADE. Postgres will refuse to delete a plan that still has subscribers.

**Encrypted API keys** — `user_api_keys.encrypted_key` is meant to store
Fernet-encrypted keys only, with `key_hint` holding the last 4 plaintext
chars for display. **`cryptography` is not yet a dependency** — encryption
code doesn't exist yet, so don't wire up `/api-keys` until it's added.

**`cost_usd_micros` as BIGINT** — Token cost stored as integer
micro-dollars (1 USD = 1_000_000) to avoid float drift when aggregating.

**`token_usage_log` is append-only** — audit trail / billing meter.
`query_history_id` is nullable for future non-query LLM calls.

### Additional table (not in prior doc)

```sql
CREATE TABLE chat_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT,
  is_archived BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- query_history gained:
ALTER TABLE query_history
  ADD COLUMN session_id UUID REFERENCES chat_sessions(id) ON DELETE SET NULL;
```

The rest of the SQL schema (users, projects, documents, chunks,
query_history, project_memory, project_insights, plans, subscriptions,
user_api_keys, token_usage_log) is unchanged from the original design and
matches `app/db/models.py` / `app/db/billing.py` field-for-field. See those
files for the authoritative column list rather than duplicating full DDL
here — it drifts easily.

---

## API Endpoints

### Auth (public) — ✅ implemented
| Method | Path | Description |
|---|---|---|
| POST | /auth/register | Create account — returns user, not token |
| POST | /auth/login | OAuth2 password form → returns JWT access token |

### Projects (protected) — ✅ implemented
| Method | Path | Description |
|---|---|---|
| POST | /projects/ | Create project for current user (409 handled as 400 "already exists" if name taken) |
| GET | /projects/ | List current user's projects with `document_count`, paginated (`skip`/`limit`) |
| GET | /projects/{id} | Get one project + documents + chat sessions (sorted by `last_active` desc) |
| DELETE | /projects/{id} | Delete project + cascade all data (204) |

### Documents — ⬜ not implemented
| Method | Path | Description |
|---|---|---|
| POST | /projects/{id}/documents | Upload file — returns 202, ingests in background |
| GET | /projects/{id}/documents | List documents with status |
| GET | /documents/{id}/status | Poll ingestion status |
| DELETE | /documents/{id} | Delete doc + file + vectors |

### Query / RAG — ⬜ not implemented
| Method | Path | Description |
|---|---|---|
| POST | /projects/{id}/query | Ask question — returns answer + lean sources |
| GET | /projects/{id}/history | Get past Q&A pairs |
| GET | /projects/{id}/insights | Get living blog post (Markdown) |

### User — ⬜ not implemented
| Method | Path | Description |
|---|---|---|
| GET | /users/me | Get current user profile |
| PATCH | /users/me/password | Change password |

### Billing — ⬜ not implemented (interface exists, no routes)
| Method | Path | Description |
|---|---|---|
| GET    | /billing/plans                | List all active plans — public |
| POST   | /billing/checkout             | Create checkout session |
| POST   | /billing/webhook              | Gateway webhook/callback receiver |
| GET    | /billing/portal               | Get self-serve billing portal URL |
| GET    | /billing/subscription         | Get current user's subscription + plan |

### Usage — ⬜ not implemented
| Method | Path | Description |
|---|---|---|
| GET    | /usage/summary                | Total tokens + cost this billing period |
| GET    | /usage/history                | Paginated per-call token log |

### API Keys — BYOK — ⬜ not implemented (blocked on adding `cryptography` dep)
| Method | Path | Description |
|---|---|---|
| GET    | /api-keys                     | List user's saved keys (hint only) |
| POST   | /api-keys                     | Save a new encrypted key for a provider |
| PATCH  | /api-keys/{provider}          | Rotate an existing key |
| DELETE | /api-keys/{provider}          | Remove a key |

---

## Key Architectural Patterns

**Ownership check — currently inlined, not yet a shared dependency.**
The original plan was a `get_project_for_user` dependency in
`app/core/deps.py`. That file doesn't exist. Today, `app/api/projects.py`
repeats `.where(models.Project.id == id, models.Project.user_id == current_user.id)`
in each route by hand. `get_current_user` itself lives in
`app/core/security.py` (not a separate `deps.py`). **When documents/query
routes are added, either keep repeating this pattern or extract the shared
dependency now** — worth deciding before the duplication spreads further.

**Document upload flow (planned, unbuilt)**
1. Save raw file to Supabase Storage
2. Create `documents` row with `status=processing`
3. Enqueue background task for ingestion
4. Return `202 Accepted` immediately
5. Frontend polls `GET /documents/{id}/status` every 2–3s until `ready`

**RAG query flow (planned, unbuilt)**
1. Embed the user's question (same model as ingestion)
2. Vector search: `WHERE project_id = X AND user_id = Y ORDER BY embedding <=> query_vector LIMIT 5`
3. Inject `project_memory.memory_text` above retrieved chunks in prompt
4. Call LLM → return answer + lean sources
5. Write to `query_history` (with `session_id` if part of a chat session, `expires_at = now() + 90 days`)
6. Fire background tasks: `update_memory()` + `maybe_update_insights()`

**Memory / insights update flow (planned, unbuilt)** — unchanged from
original design: memory updates after every query by folding new
`query_history` rows in; insights regenerate every `ProjectInsights.UPDATE_EVERY`
(=5) queries, guarded by `is_regenerating`.

**Payment gateway abstraction** — `app/billing/payment_gateway.py` defines
`PaymentGateway` ABC + `get_gateway()` factory, matching the original design.
Both `StripeGateway` and `SSLCommerzGateway` are stubs that raise
`NotImplementedError` on every method. **`get_gateway()` reads
`settings.PAYMENT_GATEWAY`, but `PAYMENT_GATEWAY` is not defined as a field
on `Settings` in `app/core/config.py`** — calling it today will raise an
`AttributeError`/validation error, not the intended `ValueError`. Add the
field before wiring up billing routes.

**Quota enforcement, webhook event mapping, BYOK key routing, token
logging, free-plan seeding** — all still just design intent from the
original doc; no route or task code exists for any of these yet.

---

## Known Gaps / Drift (from original design doc)

- `main.py` imports `init_db`/`close_db` from `app.db.database` but never
  calls them (no lifespan handler wired up). Table creation currently
  depends entirely on Alembic migrations, not on app startup.
- `settings.PAYMENT_GATEWAY` is referenced in `payment_gateway.py` but not
  declared in `Settings` — see above.
- `.env.example` is missing `SUPABASE_BUCKET_NAME` even though
  `app/core/config.py` requires it (`SUPABASE_BUCKET_NAME: str = os.getenv(...)`).
- `.env.example` also doesn't list `MAX_FILES` / `MAX_FILE_SIZE`, both
  required by `Settings`.
- README's env var table still says `STORAGE_BUCKET` — the real setting is
  `SUPABASE_BUCKET_NAME`. README also says `EMBEDDING_DIM` is an env var;
  it's actually the hardcoded `Chunk.EMBEDDING_DIM` constant.
- `drop_downs.DocumentStatus` is a plain class of string constants, unlike
  every other enum in that file (`UserRole`, `UserPlan`, etc. are all
  `str, enum.Enum`) — inconsistent, may be worth aligning later.
- README names LangGraph + Pydantic AI as the agent orchestration layer;
  this isn't reflected in `pyproject.toml` yet and no code references it.
- No LLM SDK (anthropic/openai), no embedding library, no `cryptography`,
  no `stripe`, no Celery/Redis are installed yet — all needed before the
  corresponding "not implemented" sections above can be built.
- Working tree currently has untracked `.env.local`, `uv.lock`, and a
  stray `arnaud-girault-Sbdljjw3WBI-unsplash.jpg` at repo root (unclear
  purpose — possibly a leftover download, not referenced anywhere in code).

---

## Files Written So Far

| File | Status |
|---|---|
| `app/core/config.py` | ✅ Done |
| `app/core/security.py` | ✅ Done (also holds `get_current_user`) |
| `app/core/supabase_client.py` | ✅ Done |
| `app/core/deps.py` | ⬜ Not started (planned `get_project_for_user`) |
| `app/db/database.py` | ✅ Done |
| `app/db/models.py` | ✅ Done (includes ChatSession) |
| `app/db/billing.py` | ✅ Done |
| `app/db/drop_downs.py` | ✅ Done |
| `app/db/model_utils.py` | ✅ Done |
| `app/db/crud.py` | ⬜ Not started |
| `app/api/auth.py` | ✅ Done |
| `app/api/projects.py` | ✅ Done |
| `app/api/documents.py` | ⬜ Not started |
| `app/api/query.py` | ⬜ Not started |
| `app/api/billing.py` | ⬜ Not started (only the gateway interface exists) |
| `app/api/usage.py` | ⬜ Not started |
| `app/api/api_keys.py` | ⬜ Not started |
| `app/billing/payment_gateway.py` | ✅ Interface + stubs done, no real gateway implemented |
| `app/rag/ingestor.py` | ⬜ Not started |
| `app/rag/retriever.py` | ⬜ Not started |
| `app/rag/generator.py` | ⬜ Not started |
| `app/rag/vector_store.py` | ⬜ Not started |
| `app/storage/s3.py` | ⬜ Not started (Supabase client exists, no upload/download helpers) |
| `main.py` | 🟡 Minimal — mounts auth + projects only, no lifespan |
| Frontend | ⬜ Not started |

---

## Decisions Deferred (implement later)

**Local LLM support** — Ollama integration for personal/offline use. The
(unwritten) `generator.py` should be written with a provider abstraction
from the start so swapping Claude/OpenAI/Ollama is a config change, not a
code change.

**Agent orchestration framework** — README names LangGraph + Pydantic AI,
but no design decision has been recorded yet on how they divide
responsibility (e.g. LangGraph for multi-step retrieval/tool flows,
Pydantic AI for structured LLM outputs?). Nail this down before starting
`app/rag/`.

**Table partitioning** — `query_history` can be range-partitioned by
`asked_at` if it grows very large. Not needed until scale demands it.

**Redis / Celery** — FastAPI background tasks are assumed for ingestion and
memory updates. If jobs need retries or a queue UI, migrate to Celery + Redis.
The task logic itself won't change — only the task runner.

**BYOK encryption** — Fernet-based encryption for `user_api_keys` is
designed but not implemented; needs the `cryptography` package and an
`ENCRYPTION_KEY` setting before `/api-keys` can be built.

---

## Environment Variables

### Declared in `app/core/config.py` (`Settings`)
```
DB_NAME
DB_USER
DB_PASSWORD
DB_HOST
DB_PORT
DB_ECHO                      # not in .env.example, defaults to False
SECRET_KEY
ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_JWT_SECRET
SUPABASE_BUCKET_NAME         # missing from .env.example — must be added there
MAX_FILES                    # missing from .env.example
MAX_FILE_SIZE                # missing from .env.example
```

### Referenced but not yet declared in `Settings` (will error if used)
```
PAYMENT_GATEWAY              # read by app/billing/payment_gateway.py::get_gateway()
```

### Will be needed once the corresponding features are built
```
ENCRYPTION_KEY                # Fernet key for user_api_keys.encrypted_key
```

_Last updated: 2026-07-14_
