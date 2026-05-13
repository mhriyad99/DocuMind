from uuid import UUID
from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    document_count: int