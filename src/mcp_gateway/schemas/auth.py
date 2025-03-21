from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from ..models.auth import AppType

class AppIDBase(BaseModel):
    name: str
    description: str | None = None
    type: AppType

class AppIDCreate(AppIDBase):
    pass

class AppIDResponse(AppIDBase):
    id: int
    app_id: str
    name: str
    description: Optional[str]
    type: AppType
    created_at: datetime
    is_active: bool
    last_connected: Optional[datetime]

    class Config:
        from_attributes = True

class APIKeyBase(BaseModel):
    name: str

class APIKeyCreate(APIKeyBase):
    app_id: int

class APIKeyResponse(APIKeyBase):
    id: int
    name: str
    app_id: int
    created_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True

class APIKeyWithSecret(APIKeyResponse):
    key: str = Field(..., description="The API key secret. Only shown once upon creation.")

class BridgeLogBase(BaseModel):
    level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR)")
    message: str = Field(..., description="Log message content")
    connection_id: str = Field(..., description="Bridge connection identifier")
    log_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional log context")

class BridgeLogCreate(BridgeLogBase):
    timestamp: Optional[datetime] = Field(None, description="Log timestamp, server will set if not provided")

class BridgeLogBatchCreate(BaseModel):
    logs: List[BridgeLogCreate] = Field(..., description="Batch of logs to create")

class BridgeLogResponse(BridgeLogBase):
    id: int
    app_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class BridgeLogList(BaseModel):
    total: int = Field(..., description="Total number of logs matching query")
    logs: List[BridgeLogResponse]

    class Config:
        from_attributes = True 