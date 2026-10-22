import httpx
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from app.models.user import User
from app.schemas import RegisterRequest, LoginRequest, ChatRequest
from app.models import Conversation, ChatMessage, User
from app.db.session import DbSession
from app.api.deps import user_response, token_response
from app.core.security import password_hasher, CurrentUser, verify_password, hash_password
from app.core.config import settings
from app.db.session import get_db
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from app.db.session import SessionLocal
from app.services.ollama_service import stream_ollama
from app.core.security import get_current_user

router = APIRouter()

@router.get("/")
def home():
    return {"message": "Chat API is running"}

@router.post("/auth/token", status_code=status.HTTP_200_OK)
def swagger_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.scalar(
        select(User).where(
            User.email == form_data.username
        )
    )

    if not user or not verify_password(
        form_data.password,
        user.password_hash if user else
        password_hasher.hash("dummy-password")
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    return token_response(user)
    
@router.post("/auth/register", status_code=201)
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

@router.post("/auth/login")
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

@router.get("/auth/me")
def get_me(user: CurrentUser):
    return user_response(user)

@router.get("/conversations")
def list_conversations(
    user: CurrentUser,
    db: DbSession,
):
    conversations = db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.id.desc())
    ).all()

    return [
        {
            "id": c.id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
        }
        for c in conversations
    ]

@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    user: CurrentUser,
    db: DbSession,
):
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    messages = db.scalars(
        select(ChatMessage)
        .where(
            ChatMessage.conversation_id == conversation_id
        )
        .order_by(ChatMessage.id)
    ).all()

    return {
        "id": conversation.id,
        "title": conversation.title,
        "messages": [
            {"role": m.role, "content": m.content}
            for m in messages
        ],
    }

@router.post("/chat")
async def chat(
    request: ChatRequest,
    user: CurrentUser,
    db: DbSession,
):
    if any(
        m.role not in ("user", "assistant")
        for m in request.messages
    ):
        raise HTTPException(
            status_code=400,
            detail="Unsupported message role",
        )

    if request.messages[-1].role != "user":
        raise HTTPException(
            status_code=400,
            detail="The last message must be from the user",
        )

    conversation = None

    if request.conversation_id is not None:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user.id,
            )
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )
    else:
        title = request.messages[-1].content[:200]
        conversation = Conversation(
            user_id=user.id,
            title=title or "New chat",
        )
        db.add(conversation)
        db.flush()

    ollama_messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful AI assistant. "
                "Answer clearly and accurately."
            ),
        },
        *[
            m.model_dump()
            for m in request.messages
        ],
    ]

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": ollama_messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            result = response.json()

        reply = result["message"]["content"]

        db.add_all([
            ChatMessage(
                conversation_id=conversation.id,
                role="user",
                content=request.messages[-1].content,
            ),
            ChatMessage(
                conversation_id=conversation.id,
                role="assistant",
                content=reply,
            ),
        ])
        db.commit()

        return {
            "conversation_id": conversation.id,
            "reply": reply,
            "model": result.get("model", settings.ollama_model),
        }

    except httpx.HTTPError as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="AI service unavailable. Check Ollama.",
        ) from exc
    except Exception:
        db.rollback()
        raise



# Streaming chat: authenticated users, PostgreSQL history and SSE events.
def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def _prepare_stream(user_id, payload):
    with SessionLocal.begin() as db:
        if payload.conversation_id is None:
            conv = Conversation(user_id=user_id, title=payload.message[:60])
            db.add(conv)
            db.flush()
        else:
            conv = db.scalar(select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.user_id == user_id))
            if conv is None:
                raise ValueError("Conversation not found")
        history = [{"role": m.role, "content": m.content} for m in db.scalars(
            select(ChatMessage).where(
                ChatMessage.conversation_id == conv.id,
                ChatMessage.status == "completed"
            ).order_by(ChatMessage.id)).all()]
        db.add(ChatMessage(conversation_id=conv.id, role="user",
                           content=payload.message, status="completed"))
        assistant = ChatMessage(conversation_id=conv.id, role="assistant",
                                content="", status="streaming")
        db.add(assistant)
        db.flush()
        return conv.id, assistant.id, history + [{"role": "user", "content": payload.message}]

def _save_stream(message_id, content, status):
    with SessionLocal.begin() as db:
        msg = db.get(ChatMessage, message_id)
        if msg is not None:
            msg.content = content
            msg.status = status

@router.post("/chat/stream", tags=["chat"])
async def chat_stream(payload: ChatRequest, user: User = Depends(get_current_user)):
    try:
        conversation_id, assistant_id, history = await asyncio.to_thread(
            _prepare_stream, user.id, payload)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def events():
        chunks = []
        status = "cancelled"
        try:
            yield _sse("meta", {"conversation_id": conversation_id,
                                 "assistant_message_id": assistant_id})
            async for chunk in stream_ollama(history):
                chunks.append(chunk)
                yield _sse("token", {"content": chunk})
            status = "completed"
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        except Exception:
            status = "failed"
            yield _sse("error", {"message": "Ollama generation failed"})
        finally:
            # A shielded task continues the write if request cancellation occurs.
            task = asyncio.create_task(asyncio.to_thread(
                _save_stream, assistant_id, "".join(chunks), status))
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                pass
        if status == "completed":
            yield _sse("done", {"conversation_id": conversation_id,
                                "assistant_message_id": assistant_id})

    return StreamingResponse(events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
