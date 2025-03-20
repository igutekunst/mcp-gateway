from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    version: str
    started_at: str
    uptime_seconds: float

_start_time = datetime.utcnow()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint that returns system status
    """
    now = datetime.utcnow()
    uptime = (now - _start_time).total_seconds()
    
    return HealthResponse(
        status="healthy",
        version="0.1.0",  # We should get this from package metadata
        started_at=_start_time.isoformat(),
        uptime_seconds=uptime
    ) 