from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from sqlalchemy import select, func

from app.core.security import get_current_user
from app.db.database import get_db
from app.schemas import projects
from app.db import models

router = APIRouter(
    prefix="/projects",
    tags=["Projects"],
)

@router.get("/", response_model=List[projects.ProjectOut])
async def get_projects(skip: int = 0, limit: int = 25,
                 current_user: models.User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db)):

    result = await db.scalars(
        select(models.Project,
               select(func.count(models.Document.id))
                      .where(models.Document.project_id == models.Project.id)
                      .correlate(models.Project)
                      .scalar_subquery()
                      .label("document_count"))
        .where(models.Project.id == current_user.id)
        .limit(limit)
        .offset(skip)
    )

    user_projects = result.all()

    return [
        projects.ProjectOut(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            updated_at=project.updated_at,
            document_count=project.document_count
        )
        for project in user_projects
    ]