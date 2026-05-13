import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import EmailStr
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    Enum,
    func,
)
from app.db.database import Base
from app.db import drop_downs
from app.db.model_utils import uuid_pk, now_utc


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[EmailStr] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[drop_downs.UserRole] = mapped_column(Enum(drop_downs.UserRole, name="user_roles"),
                                           nullable=False, default=drop_downs.UserRole.USER)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc()
    )

    #relationships
    projects: Mapped[list["Project"]] = relationship(
        "Project", back_populates="owner", cascade="all, delete-orphan", lazy="noload"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="owner", cascade="all, delete-orphan", lazy="noload"
    )
    query_history: Mapped[list["QueryHistory"]] = relationship(
        "QueryHistory", back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )
    subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription", back_populates="user", uselist=False, lazy="noload"
    )
    api_keys: Mapped[list["UserApiKey"]] = relationship(
        "UserApiKey", back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )
    token_usage: Mapped[list["TokenUsageLog"]] = relationship(
        "TokenUsageLog", back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc(), onupdate=now_utc()
    )

    #relationships
    owner: Mapped["User"] = relationship("User", back_populates="projects", lazy="noload")
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan", lazy="noload"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="project", cascade="all, delete-orphan", lazy="noload"
    )
    query_history: Mapped[list["QueryHistory"]] = relationship(
        "QueryHistory", back_populates="project", cascade="all, delete-orphan", lazy="noload"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=drop_downs.DocumentStatus.PROCESSING,
        index=True,
    )
    chunk_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc()
    )

    # relationships
    project: Mapped["Project"] = relationship("Project", back_populates="documents", lazy="noload")
    owner: Mapped["User"] = relationship("User", back_populates="documents", lazy="noload")
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan", lazy="noload"
    )


class Chunk(Base):

    __tablename__ = "chunks"

    EMBEDDING_DIM = 768

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    chunk_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc()
    )

    #relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks", lazy="noload")
    project: Mapped["Project"] = relationship("Project", back_populates="chunks", lazy="noload")


class QueryHistory(Base):
    """
        Stores every question a user asked and the LLM answer returned.

        Bloat prevention decisions made here:
        ─────────────────────────────────────
        1. `sources` stores ONLY doc_id, filename, score — no chunk text.
           Full chunk text can be re-fetched from the chunks table by doc_id
           if ever needed. This keeps each row small.

        2. `expires_at` enables a retention policy. A scheduled job (cron /
           pg_cron) deletes rows WHERE expires_at < now(). Set it to
           now() + 90 days on insert. Adjust per your needs.

        3. Composite index on (user_id, project_id, asked_at DESC) covers the
           most common query pattern: "give me this user's recent history for
           this project", sorted newest first.

        Alembic note — add this to your migration for table partitioning later:
        ─────────────────────────────────────────────────────────────────────────
        When you have heavy traffic, convert this to a range-partitioned table
        by asked_at. For now, the expires_at + index approach is sufficient.

        sources shape (lean — no chunk text):
            [
                {"doc_id": "uuid", "filename": "policy.pdf", "score": 0.91},
                {"doc_id": "uuid", "filename": "report.pdf", "score": 0.87},
            ]
        """

    __tablename__ = "query_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        default=None,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    # Lean snapshot — doc_id, filename, score only. No chunk text.
    sources: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # How many chunks were retrieved for this query (useful for debugging)
    retrieved_chunks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    asked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Retention — set to asked_at + 90 days on insert.
    # A pg_cron job runs: DELETE FROM query_history WHERE expires_at < now();
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # Composite index — covers "latest history for a user's project" queries
    __table_args__ = (
        Index(
            "ix_query_history_user_project_asked",
            "user_id",
            "project_id",
            asked_at.desc(),
        ),
    )

    # relationships
    project: Mapped["Project"] = relationship(  # noqa: F821
        "Project", back_populates="query_history", lazy="noload"
    )
    user: Mapped["User"] = relationship(  # noqa: F821
        "User", back_populates="query_history", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<QueryHistory id={self.id} project={self.project_id} asked_at={self.asked_at}>"


class ProjectMemory(Base):
    """
        One row per project. Stores a continuously compressed summary of everything
        the user has asked and discovered in this project — injected into every
        future RAG prompt as long-term context.

        How it works:
        ─────────────
        1. User makes a query → RAG response is returned normally.
        2. A background task fires AFTER the response.
        3. The task reads the last N rows from query_history for this project.
        4. It asks the LLM to merge those queries into the existing `memory_text`,
           producing a refreshed, compressed summary.
        5. `memory_text` is updated in place. Version is incremented.

        The RAG prompt then becomes:
            [Long-term memory]   ← memory_text injected here
            [Retrieved chunks]   ← top-k similarity search results
            [User question]      ← current query

        memory_text shape (plain prose, LLM-generated):
            "The user is researching refund policies, return windows, and
             international shipping rules. They have shown particular interest
             in edge cases around digital products. Key findings so far: ..."

        query_cursor tracks the last query_history row that was included in the
        memory so the background task only processes new rows, not all history.

        token_count is stored so the RAG pipeline can trim memory_text if it
        would push the prompt over the model's context limit.
    """
    __tablename__ = "project_memory"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # exactly one memory row per project
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # The compressed, evolving memory — plain prose injected into RAG prompts
    memory_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Approximate token count of memory_text — used by RAG to respect context limits
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # How many queries have been folded into the current memory
    queries_absorbed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # The asked_at timestamp of the last query_history row included in this memory.
    # Background task only processes rows WHERE asked_at > query_cursor.
    query_cursor: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # How many times the memory has been regenerated — useful for debugging
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Rebuild trigger — set to True to force a full memory rebuild on next query
    # instead of an incremental update. Useful if memory drifts or corrupts.
    needs_rebuild: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # relationship
    project: Mapped["Project"] = relationship(  # noqa: F821
        "Project", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectMemory project={self.project_id} "
            f"version={self.version} tokens={self.token_count}>"
        )


class ProjectInsights(Base):
    """
        One row per project. Stores a living blog-style summary post that grows
        and updates as the user continues querying their documents.

        How it works:
        ─────────────
        1. After every query (or every N queries — controlled by UPDATE_EVERY),
           a background task regenerates the insight post for this project.
        2. The LLM reads recent query_history + the existing insight post and
           produces an updated Markdown document — adding new findings, updating
           existing sections, and restructuring if needed.
        3. The result is stored in `content` (Markdown).
        4. GET /projects/{id}/insights returns this content.
        5. The frontend renders it as a styled read-only webpage.

        Content shape (LLM-generated Markdown):
            # Research Insights — Legal Docs Q3
            _Last updated: 12 May 2026_

            ## Key Themes
            Your research has focused primarily on refund policies...

            ## Important Findings
            - Digital products are excluded from the standard 30-day window...

            ## Open Questions
            - The policy for international returns remains unclear...

            ## Documents Referenced
            - policy.pdf, terms.pdf, shipping-guide.pdf

        UPDATE_EVERY controls how often the post regenerates.
        Set to 1 to update after every single query (expensive but always fresh).
        Set to 5 to update every 5 queries (cheaper, slight lag).

        is_published lets the user toggle visibility — they might not want the
        insights page active until they feel they have enough queries in.

        word_count is stored so the frontend can show a "reading time" estimate
        without parsing the full Markdown on every request.
    """

    __tablename__ = "project_insights"

    # Regenerate the insight post every N queries
    UPDATE_EVERY: int = 5

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # exactly one insight post per project
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # The living blog post — stored as Markdown, rendered on the frontend
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Plain-text title extracted/generated for the post
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Approximate word count — lets frontend show "5 min read" without parsing content
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Total number of queries that have shaped this insight post so far
    queries_incorporated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # How many times the post has been regenerated
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Which documents have contributed to this post (snapshot of filenames)
    # Shape: ["policy.pdf", "terms.pdf", "shipping-guide.pdf"]
    source_documents: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # User can toggle whether the insights page is visible/shareable
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Set to True when a regeneration is currently in progress —
    # prevents duplicate background tasks firing concurrently
    is_regenerating: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # relationship
    project: Mapped["Project"] = relationship(  # noqa: F821
        "Project", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectInsights project={self.project_id} "
            f"version={self.version} published={self.is_published}>"
        )


