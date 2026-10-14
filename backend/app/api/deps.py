from app.models.user import User
from app.core.security import create_access_token


def user_response(user: User) -> dict:
    return {"id": user.id, "email": user.email}


def token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": user_response(user),
    }