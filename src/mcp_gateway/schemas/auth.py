from datetime import datetime
from pydantic import BaseModel, Field
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
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

class APIKeyBase(BaseModel):
    name: str

class APIKeyCreate(APIKeyBase):
    app_id: int

class APIKeyResponse(APIKeyBase):
    id: int
    created_at: datetime
    last_used_at: datetime | None = None
    is_active: bool
    app_id: int

    class Config:
        from_attributes = True

class APIKeyWithSecret(APIKeyResponse):
    key: str = Field(..., description="The API key secret. Only shown once upon creation.") 