from uuid import UUID
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class ProjectListOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    document_count: int

class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str]


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    status: str
    chunk_count: Optional[int]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: UUID
    question: str
    answer: str
    sources: Optional[dict]
    asked_at: datetime


class ChatSessionOut(BaseModel):
    session_id: UUID
    title: str
    last_active: datetime


class ProjectDetailOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    documents: List[DocumentOut]
    chat_sessions: List[ChatSessionOut]
    document_count: int