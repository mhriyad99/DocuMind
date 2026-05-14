from uuid import UUID
from typing import Optional
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

class ProjectDetailOut(BaseModel):
    pass