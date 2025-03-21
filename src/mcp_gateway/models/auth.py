from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum, JSON
import enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .base import Base
from enum import Enum
from pydantic import BaseModel

class AppType(str, enum.Enum):
    TOOL_PROVIDER = "tool_provider"
    AGENT = "agent"

class AppIDCreate(BaseModel):
    name: str
    type: AppType
    description: str | None = None

class APIKeyCreate(BaseModel):
    name: str
    app_id: int

class AppID(Base):
    __tablename__ = "app_ids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[AppType] = mapped_column(String(13), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_connected: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="app", cascade="all, delete-orphan")
    logs: Mapped[list["BridgeLog"]] = relationship("BridgeLog", back_populates="app", cascade="all, delete-orphan")

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    key_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    app_id = Column(Integer, ForeignKey("app_ids.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    app = relationship("AppID", back_populates="api_keys")

class BridgeLog(Base):
    __tablename__ = "bridge_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_id: Mapped[int] = mapped_column(Integer, ForeignKey("app_ids.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False)  # DEBUG, INFO, WARNING, ERROR
    message: Mapped[str] = mapped_column(String, nullable=False)
    connection_id: Mapped[str] = mapped_column(String, nullable=False)
    log_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    app = relationship("AppID", back_populates="logs") 