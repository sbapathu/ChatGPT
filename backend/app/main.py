
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import httpx
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import  Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from pwdlib import PasswordHash
from sqlalchemy import create_engine, String, Integer, DateTime, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

app = FastAPI(title="ChatGPT Local API", version="1.0.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


# ---------- Configuration ----------

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("Set the JWT_SECRET_KEY environment variable.")

ALGORITHM = "HS256"
TOKEN_MINUTES = 30
OLLAMA_URL = os.getenv( "OLLAMA_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "llama3.2")

DATABASE_URL = os.getenv( "DATABASE_URL", "sqlite:///./users.db")

engine_args = (
    {"connect_args": {"check_same_thread": False}}
    if DATABASE_URL.startswith("sqlite")
    else {}
)
engine = create_engine(DATABASE_URL, **engine_args)


# ---------- Database ----------

class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    email: Mapped[str] = mapped_column(
        String(254), unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(512)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


Base.metadata.create_all(bind=engine)


def get_db():
    with Session(engine) as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]


# ---------- Passwords and JWT ----------

password_hasher = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login"
)

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    return password_hasher.verify(password, hashed_password)

def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_MINUTES),
    }
    return jwt.encode(
        payload, SECRET_KEY, algorithm=ALGORITHM
    )

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, SECRET_KEY, algorithms=[ALGORITHM]
        )
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise unauthorized
        user_id = int(subject)
    except (InvalidTokenError, ValueError, TypeError):
        raise unauthorized

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------- API schemas ----------

class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class Message(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=20000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(
        min_length=1, max_length=50
    )


def user_response(user: User) -> dict:
    return {"id": user.id, "email": user.email}


def token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": user_response(user),
    }


# ---------- FastAPI ----------

@app.get("/")
def home():
    return {"message": "Chat API is running"}

@app.post("/api/auth/register", status_code=201)
def register(data: RegisterRequest, db: DbSession):
    email = data.email.strip().lower()

    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(
            status_code=422, detail="Enter a valid email address."
        )

    existing = db.scalar(
        select(User).where(User.email == email)
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    user = User(
        email=email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not create account. Try again.",
        )

    return token_response(user)

@app.post("/api/auth/login")
def login(data: LoginRequest, db: DbSession):
    email = data.email.strip().lower()
    user = db.scalar(
        select(User).where(User.email == email)
    )

    if not user or not verify_password(
        data.password,
        user.password_hash if user else
        password_hasher.hash("dummy-password"),
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_response(user)


@app.get("/api/auth/me")
def get_me(user: CurrentUser):
    return user_response(user)


@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    user: CurrentUser,
):
    # Only allow user/assistant messages from the client.
    if any(
        message.role not in ("user", "assistant")
        for message in request.messages
    ):
        raise HTTPException(
            status_code=400, detail="Unsupported message role"
        )

    if request.messages[-1].role != "user":
        raise HTTPException(
            status_code=400,
            detail="The last message must be from the user",
        )

    messages = [{
        "role": "system",
        "content": (
            "You are a helpful AI assistant. "
            "Answer clearly and accurately."
        ),
    }]
    messages.extend(
        message.model_dump()
        for message in request.messages
    )

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": MODEL_NAME,
                    "messages": messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

        return {
            "reply": data["message"]["content"],
            "model": data.get("model", MODEL_NAME),
        }

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI service unavailable. Check Ollama.",
        ) from exc
