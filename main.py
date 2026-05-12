from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from app.db.database import init_db, close_db

from app.api import auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(lifespan=lifespan)

app.include_router(auth.router)
@app.get("/")
async def root():
    return {"message": "Hello World"}