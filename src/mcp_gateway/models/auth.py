from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum
import enum
from sqlalchemy.orm import relationship
from .base import Base

class AppType(enum.Enum):
    TOOL_PROVIDER = "tool_provider"
    AGENT = "agent"

class AppID(Base):
    __tablename__ = "app_ids"

    id = Column(Integer, primary_key=True)
    app_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    type = Column(Enum(AppType), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    api_keys = relationship("APIKey", back_populates="app")

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