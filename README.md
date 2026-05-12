# DocuMind

A multi-tenant RAG (Retrieval-Augmented Generation) system where users create projects, upload documents, and query an LLM for answers grounded in their own data. Every user's data is fully isolated. Supports cloud LLMs (Claude, OpenAI) and local LLMs (Ollama).

---

## Tech Stack

| Layer            | Choice                           |
|------------------|----------------------------------|
| Backend          | FastAPI + asyncpg                |
| ORM              | SQLAlchemy (async)               |
| Database         | PostgreSQL + pgvector (Supabase) |
| Migrations       | Alembic                          |
| File Storage     | Supabase Storage                 |
| LLM              | Claude / OpenAI / Ollama         |
| Agent Orcastator | Langraph + Pydantic AI           |

---

## Getting Started

### 1. Install dependencies

```bash
pip install uv
uv sync
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Fill in your values
```

### 3. Set up the database

Run a local Supabase instance (see [SUPABASE_SELFHOST_GUIDE.md]((guide/SUPABASE_SELFHOST_GUIDE.md))), then apply migrations:

```bash
alembic upgrade head
```

### 4. Run the server

```bash
uvicorn app.main:app --port <your-prefered-port> --reload
```

---

## API Overview

| Group | Base Path | Description |
|---|---|---|
| Auth | `/auth` | Register and login |
| Projects | `/projects` | Create and manage projects |
| Documents | `/projects/{id}/documents` | Upload and track ingestion |
| Query | `/projects/{id}/query` | Ask questions, view history |
| User | `/users/me` | Profile and password |

---

## Environment Variables

| Variable | Description |
|---|---|
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | Database user |
| `DB_PASSWORD` | Database password |
| `DB_HOST` | Database host |
| `DB_PORT` | Database port |
| `SECRET_KEY` | JWT signing secret |
| `ALGORITHM` | JWT algorithm (e.g. HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry duration |
| `STORAGE_BUCKET` | Supabase storage bucket name |
| `EMBEDDING_DIM` | Embedding dimension (768) |