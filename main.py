from fastapi import FastAPI, Depends
from app.db.database import init_db, close_db

from app.api import auth

app = FastAPI()

app.include_router(auth.router)
@app.get("/")
async def root():
    return {"message": "Hello World"}