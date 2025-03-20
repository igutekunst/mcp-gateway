from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class BridgeConnectionResponse(BaseModel):
    """Response for successful bridge connection"""
    connection_id: str
    ws_url: str  # WebSocket URL for MCP communication
    message: str

@router.post("/bridge/connect")
async def connect_bridge(
    api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Initial connection endpoint for bridge clients.
    Returns connection details including WebSocket URL for MCP communication.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key is required"
        )
    
    # TODO: Validate API key against database
    
    # For now, just return a simple response
    return BridgeConnectionResponse(
        connection_id="test-connection",
        ws_url="ws://localhost:8000/api/bridge/ws",
        message="Bridge connected successfully. Use the ws_url for MCP communication."
    ) 