from fastapi import FastAPI, Depends
from app.db.database import init_db, close_db

from app.api import auth, projects

app = FastAPI()

app.include_router(auth.router)
app.include_router(projects.router)
@app.get("/")
async def root():
    return {"message": "Hello World"}