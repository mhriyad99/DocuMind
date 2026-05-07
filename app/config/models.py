import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    func,
)
from app.config.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )

def now_utc():
    return func.now()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
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


class DocumentStatus:
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

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
        default=DocumentStatus.PROCESSING,
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
    """
    One row per text chunk extracted from a document.

    The `embedding` column is a pgvector vector — requires:
        CREATE EXTENSION IF NOT EXISTS vector;

    Dimension (1536) matches OpenAI text-embedding-3-small / ada-002.
    Change to 1024 for Cohere embed-v3, or 768 for many open-source models.

    Index (created via Alembic or init_db):
        CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
    SQLAlchemy cannot create HNSW indexes declaratively yet — add it in your
    Alembic migration manually (see comment at bottom of this file).
    """
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