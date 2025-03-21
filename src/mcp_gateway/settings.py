from pydantic_settings import BaseSettings
from pydantic import SecretStr
import secrets
from pathlib import Path
import os
from typing import Optional

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Admin authentication
    ADMIN_PASSWORD_HASH: Optional[str] = None
    COOKIE_SECRET: str = secrets.token_urlsafe(32)
    ALLOW_INSECURE: bool = False
    SESSION_EXPIRE_MINUTES: int = 60
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///data/mcp-gateway.db"
    
    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    class Config:
        env_prefix = "MCP_"
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get settings instance - useful for dependency injection."""
    return settings

def verify_admin_password(password: str) -> bool:
    """Verify the admin password against stored hash."""
    if not settings.ADMIN_PASSWORD_HASH:
        return False
        
    import bcrypt
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            settings.ADMIN_PASSWORD_HASH.encode('utf-8')
        )
    except Exception:
        return False

def hash_password(password: str) -> str:
    """Hash a password for storage."""
    import bcrypt
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def initialize_admin_password(password: str) -> None:
    """Initialize or update the admin password."""
    settings.ADMIN_PASSWORD_HASH = hash_password(password) 