from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class AdminLoginRequest(BaseModel):
    """Request schema for admin login."""
    password: str = Field(..., description="Admin password")

class AdminSession(BaseModel):
    """Schema for admin session information."""
    token: str = Field(..., description="Session token")
    expires_at: datetime = Field(..., description="Session expiration timestamp")

class AdminSessionResponse(BaseModel):
    """Response schema for admin session."""
    expires_at: datetime = Field(..., description="Session expiration timestamp") 