from fastapi import APIRouter, HTTPException, Depends, status, Response
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

@router.get("/", response_model=List[projects.ProjectListOut])
async def get_projects(skip: int = 0, limit: int = 25,
                 current_user: models.User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db)):

    result = await db.execute(
        select(models.Project,
               select(func.count(models.Document.id))
                      .where(models.Document.project_id == models.Project.id)
                      .correlate(models.Project)
                      .scalar_subquery()
                      .label("document_count"))
        .where(models.Project.user_id == current_user.id)
        .limit(limit)
        .offset(skip)
    )

    user_projects = result.all()

    return [
        projects.ProjectListOut(
            id=project.id,
            name=project.name,
            description=project.description,
            created_at=project.created_at,
            updated_at=project.updated_at,
            document_count=doc_count
        )
        for project, doc_count in user_projects
    ]

@router.post("/", response_model=projects.ProjectOut)
async def create_project(payload: projects.ProjectCreate,
                         db: AsyncSession = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)):

    existing_project = await db.scalar(
        select(models.Project)
        .where(models.Project.user_id == current_user.id,
               models.Project.name == payload.name)
    )

    if existing_project:
        raise HTTPException(status_code=400, detail="Project already exists")

    new_project = models.Project(
        name=payload.name,
        user_id=current_user.id,
        description=payload.description,
    )

    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)

    return new_project


@router.get("/{id}", response_model=projects.ProjectDetailOut)
async def get_project_details(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = await db.scalar(
        select(models.Project).where(
            models.Project.id == id,
            models.Project.user_id == current_user.id,
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    doc_result = await db.execute(
        select(models.Document)
        .where(models.Document.project_id == id)
        .order_by(models.Document.created_at.desc())
    )
    documents = doc_result.scalars().all()

    chat_session = await db.execute(
        select(models.ChatSession)
        .where(models.ChatSession.project_id == id)
    )
    chat_sessions = chat_session.scalars().all()

    chat_sessions = [
        projects.ChatSessionOut(
            session_id=session.id,
            title=session.title,
            last_active=session.updated_at
        )
        for session in chat_sessions
        ]

    chat_sessions.sort(key=lambda s: s.last_active, reverse=True)

    return projects.ProjectDetailOut(
        id=project.id,
        name=project.name,
        description=project.description,
        created_at=project.created_at,
        updated_at=project.updated_at,
        documents=[projects.DocumentOut.model_validate(d) for d in documents],
        chat_sessions=chat_sessions,
        document_count=len(documents),
    )

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(id: str, db: AsyncSession = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)):
    project = await db.scalar(
        select(models.Project)
        .where(models.Project.id == id,
               models.Project.user_id == current_user.id,)
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await db.delete(project)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)

