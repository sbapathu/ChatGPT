from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    app_name: str = "ChatGPT Clone API"
    db_url : str= "postgresql+psycopg://chatgpt_user:pwd@localhost:5432/chatgpt_clone"
    db_user_pwd: str = os.getenv("DB_USER_PWD", "xxxxxxxxx")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    cors_origins: list[str] = ["http://localhost:5173"]
    auto_create_tables: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
