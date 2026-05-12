from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db.database import init_db, close_db
from app.db import models

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Hello World"}