from pydantic import BaseModel, Field

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
    conversation_id: int | None = None
