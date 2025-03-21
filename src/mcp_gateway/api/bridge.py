from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json
from typing import Dict, Optional
import uuid
import logging
from ..models.base import get_db
from ..models.auth import AppID, APIKey
from ..services.auth import AuthService
from ..core.bridge import MCPBridge
from ..tools import ToolRegistry

router = APIRouter()
logger = logging.getLogger(__name__)

# Store active bridge connections
bridge_connections: Dict[str, MCPBridge] = {}

@router.post("/heartbeat")
async def bridge_heartbeat(
    request: dict,
    api_key: str = Depends(AuthService.get_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Handle bridge heartbeat"""
    try:
        # Update last_connected timestamp
        auth_service = AuthService(db)
        app = await auth_service.get_app_by_api_key(api_key)
        if not app:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        app.last_connected = datetime.utcnow()
        await db.commit()
        
        return {
            "status": "ok",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Heartbeat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/connect")
async def handle_websocket(
    websocket: WebSocket,
    api_key: str = Depends(AuthService.get_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Handle WebSocket connection for bridge"""
    connection_id = None
    try:
        logger.info("New WebSocket connection attempt")
        await websocket.accept()
        
        connection_id = f"bridge-{len(bridge_connections) + 1}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"Generated connection_id: {connection_id}")
        
        bridge = MCPBridge(websocket, connection_id)
        bridge_connections[connection_id] = bridge
        
        # Use bridge's response method consistently
        logger.info("Sending connection established message")
        await bridge._send_response({
            "type": "connection_established",
            "connection_id": connection_id,
            "message": "Bridge connected successfully"
        }, "connection")  # Explicitly pass "connection" as the ID

        while True:
            try:
                message = await websocket.receive_json()
                logger.debug(f"Received WebSocket message: {message}")
                await bridge.handle_message(message)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for connection {connection_id}")
                break
            except Exception as e:
                logger.error(f"Error handling message: {str(e)}")
                continue
    except WebSocketDisconnect:
        logger.info(f"Bridge {connection_id} disconnected")
        if connection_id in bridge_connections:
            del bridge_connections[connection_id]
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        if connection_id and connection_id in bridge_connections:
            del bridge_connections[connection_id] 