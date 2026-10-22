from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from typing import Literal

class Message(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=20000)

class ChatRequest(BaseModel):
    messages: list[Message] = Field(
        min_length=1, max_length=50
    )
    conversation_id: int | None = None
    
class ChatStreamRequest(BaseModel):
    message: str = Field(
        min_length=1, max_length=50
    )
    conversation_id: int | None = None

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    model_config = {"from_attributes": True}

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: int | None = None

class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    model: str

class MessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    status: str = "completed"
    model_config = {"from_attributes": True}

class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse]
