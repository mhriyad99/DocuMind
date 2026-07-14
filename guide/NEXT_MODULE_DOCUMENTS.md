# Next Module: Documents (Upload & Ingestion Skeleton)

> Implementation plan for the next unbuilt module. See
> [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for full project state — this
> file only covers Documents.

## Why this module, and why now

Dependency chain per `PROJECT_CONTEXT.md`:

```
Auth ✅ → Projects ✅ → Documents ⬜ → RAG (chunk/embed/retrieve) ⬜ → Query ⬜
```

`chunks` can't exist without a `documents` row to point to, and `/query`
can't be tested without real chunks. Documents is the next unblocked piece
and the shortest path to an end-to-end demo (upload → status → eventually
query).

**Scope for this pass**: file upload to Supabase Storage, a `documents` row
per file, status polling, and delete. Actual parsing/chunking/embedding is
**out of scope** — the background task only flips `status` from
`processing` → `ready` (stub) so the full HTTP flow works. Real ingestion
logic belongs to the RAG module, wired in later without changing this API.

---

## Step 1 — Storage helper: `app/storage/s3.py`

Despite the filename (kept for parity with the original design doc), this
wraps the Supabase client from `app/core/supabase_client.py`, not S3.

- `async def upload_file(user_id: UUID, project_id: UUID, filename: str, content: bytes) -> str`
  Builds a storage path like `{user_id}/{project_id}/{uuid4()}_{filename}`
  (never trust the raw filename alone — collisions and path traversal).
  Uploads via `supabase.storage.from_(settings.SUPABASE_BUCKET_NAME).upload(...)`.
  Returns the storage path to save on `Document.storage_path`.
- `async def delete_file(storage_path: str) -> None`
  Wraps `supabase.storage.from_(...).remove([storage_path])`.
- Raise a plain `ValueError`/`RuntimeError` on failure — let the route layer
  translate to an HTTP error. Don't swallow exceptions here.

The Supabase Python SDK's storage calls are sync; either run them in a
threadpool (`asyncio.to_thread`) or confirm the installed `supabase` version
exposes an async storage client before assuming `await` works directly.

---

## Step 2 — Schemas: `app/schemas/documents.py`

`DocumentOut` already exists in `app/schemas/projects.py:26` — reuse it,
don't redefine. Add a new file for the rest:

```python
class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    status: str

class DocumentStatusOut(BaseModel):
    id: UUID
    status: str
    chunk_count: Optional[int]
    error_message: Optional[str]
```

---

## Step 3 — Shared ownership dependency: `app/core/deps.py`

`PROJECT_CONTEXT.md` flags that `app/api/projects.py` inlines the ownership
filter in every route instead of using the originally-planned
`get_project_for_user` dependency. Documents routes need the same check
twice as often (once for the project, implicitly for every document under
it) — extract it now instead of copy-pasting a third time:

```python
async def get_project_for_user(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Project:
    project = await db.scalar(
        select(models.Project).where(
            models.Project.id == id,
            models.Project.user_id == current_user.id,
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
```

Refactor `app/api/projects.py` to use it too, so there's one ownership
check in the codebase, not two copies that can drift apart.

---

## Step 4 — Quota enforcement (light touch)

`Settings.MAX_FILES` and `Settings.MAX_FILE_SIZE` already exist
(`app/core/config.py:31-32`) and are set in `.env`. Enforce both in the
upload route before touching storage:

- Reject with `413` if `len(await file.read()) > settings.MAX_FILE_SIZE`.
- Reject with `400`/`403` if
  `count(documents WHERE project_id == id) >= settings.MAX_FILES`.

This is separate from the `plans.max_documents_per_project` billing quota
(that's per-subscription and belongs to the billing module) — these two
settings are a global hard cap, not a plan feature.

---

## Step 5 — Routes: `app/api/documents.py`

```python
router = APIRouter(prefix="/projects/{id}/documents", tags=["Documents"])
```

| Method | Path | Behavior |
|---|---|---|
| POST | `/projects/{id}/documents` | `UploadFile` param. Validate size/quota → upload to storage → insert `Document(status=PROCESSING)` → commit → enqueue `BackgroundTasks` ingestion stub → return `202` with `DocumentUploadResponse` |
| GET | `/projects/{id}/documents` | List documents for the project, ordered `created_at desc` (mirrors the query already inlined in `projects.get_project_details`) |
| GET | `/documents/{doc_id}/status` | Separate router, no project id in path — look up by `doc_id` + verify `document.user_id == current_user.id` directly (no project lookup needed) |
| DELETE | `/documents/{doc_id}` | Verify ownership, call `delete_file(storage_path)`, then `db.delete(document)` (cascades to `chunks` per existing FK) |

Use `models.Project = Depends(get_project_for_user)` from Step 3 on the
project-scoped routes.

---

## Step 6 — Ingestion stub (background task)

Not real ingestion — just closes the async loop so status polling works
end-to-end before the RAG module exists:

```python
async def stub_ingest(document_id: UUID):
    async with AsyncSessionLocal() as db:
        doc = await db.get(models.Document, document_id)
        doc.status = drop_downs.DocumentStatus.READY
        doc.chunk_count = 0
        await db.commit()
```

Fired via `BackgroundTasks.add_task(stub_ingest, new_doc.id)` in the upload
route. When the RAG module lands, replace the body of this function with
real parse → chunk → embed → store logic; the route layer doesn't change.

---

## Step 7 — Wire up `main.py`

Two things, since both are currently broken/missing per `PROJECT_CONTEXT.md`:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(lifespan=lifespan)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(documents.router)
```

`init_db()`/`close_db()` are already imported in `main.py` but never
called — fix that as part of this module rather than leaving it broken
further into the project.

---

## Step 8 — Alembic

No model changes needed — `documents` and `chunks` tables already exist
from the initial migration. Skip this step unless Step 4/5 reveals a
missing column (e.g. if you decide to store `uploaded_by` separately from
`user_id`, which you shouldn't — reuse the existing column).

---

## Step 9 — Manual test plan

```bash
uvicorn app.main:app --reload
# 1. register + login → grab access token
# 2. POST /projects/ → grab project id
# 3. POST /projects/{id}/documents (multipart file) → expect 202, status=processing
# 4. GET /documents/{doc_id}/status → poll until status=ready
# 5. GET /projects/{id}/documents → confirm it lists with chunk_count=0
# 6. DELETE /documents/{doc_id} → confirm file removed from Supabase bucket + row gone
# 7. DELETE /projects/{id} → confirm cascade removes any remaining documents
```

Also re-check `GET /projects/{id}` (existing route) still returns the new
documents correctly — it already queries `documents` for the detail view.

---

## Explicitly out of scope (next module after this)

- Real parsing (PDF/DOCX/txt extraction), chunking, embedding — `app/rag/ingestor.py`.
- Vector storage / similarity search — `app/rag/vector_store.py`, `retriever.py`.
- `/projects/{id}/query` and everything in the RAG query flow.

Once this module is done, the natural next step is `app/rag/` per
`PROJECT_CONTEXT.md`'s "Decisions Deferred → Agent orchestration
framework" — that decision (LangGraph vs. Pydantic AI responsibilities)
should be settled before writing `ingestor.py`/`generator.py`, not during.
