from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import router
from app.db.base import Base
from app.db.session import engine
from app.models import User, Conversation, ChatMessage  # register models

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"],
    allow_credentials=True, 
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router, prefix="/api/v1")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def startup():
    # Local-development convenience; use Alembic migrations in production.
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)

