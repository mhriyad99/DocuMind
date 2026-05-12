from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas import user
from app.core.security import password_hash, create_access_token
from app.db import database, models

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post("/register", response_model=user.UserRegisterResponse)
async def register(payload: user.UserRegister,
                   db: AsyncSession=Depends(database.get_db)):

    existing_user = await db.scalar(
        select(models.User)
        .where(models.User.email == payload.email)
    )

    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Email already registered")

    hashed_password = password_hash.hash(payload.password)
    new_user = models.User(
        email=payload.email,
        hashed_password=hashed_password,
        full_name=payload.fullname
    )

    db.add(new_user)
    await db.commit()

    return new_user

@router.post("/login", response_model=user.Token)
async def login(user_credentials: OAuth2PasswordRequestForm=Depends(),
                db: AsyncSession=Depends(database.get_db)):

    existing_user = await db.scalar(
        select(models.User)
        .where(models.User.email == user_credentials.username)
    )
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid username or password")


    if not password_hash.verify(user_credentials.password, existing_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid username or password")

    access_token = create_access_token(data={"id": existing_user.id})

    return {"access_token": access_token}