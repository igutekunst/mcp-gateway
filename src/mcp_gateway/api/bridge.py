from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json
from typing import Dict, Optional, List
import uuid
import logging
import os
from ..models.base import get_db
from ..models.auth import AppID, APIKey
from ..services.auth import AuthService
from ..core.bridge import MCPBridge
from ..tools import ToolRegistry
from ..schemas.auth import BridgeLogBatchCreate, BridgeLogList, BridgeLogResponse

router = APIRouter()

# Configure logging to only write to file
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # Prevent output to stdout
logger.setLevel(logging.DEBUG)

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Add file handler for bridge API logs
file_handler = logging.FileHandler("logs/bridge_api.log")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

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
    bridge = None
    try:
        logger.info("New WebSocket connection attempt")
        await websocket.accept()
        
        # Get app from API key
        auth_service = AuthService(db)
        app = await auth_service.get_app_by_api_key(api_key)
        if not app:
            await websocket.close(code=4001, reason="Invalid API key")
            return
        
        connection_id = f"bridge-{len(bridge_connections) + 1}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"Generated connection_id: {connection_id}")
        
        bridge = MCPBridge(websocket, connection_id, app.id, api_key)
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
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        if bridge:
            await bridge.cleanup()
        if connection_id and connection_id in bridge_connections:
            del bridge_connections[connection_id]

@router.post("/logs", response_model=List[BridgeLogResponse])
async def create_logs(
    logs: BridgeLogBatchCreate,
    api_key: str = Depends(AuthService.get_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Create multiple log entries."""
    try:
        auth_service = AuthService(db)
        app = await auth_service.get_app_by_api_key(api_key)
        if not app:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        created_logs = await auth_service.create_logs(app.id, logs)
        return created_logs
    except Exception as e:
        logger.error(f"Error creating logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/{app_id}", response_model=BridgeLogList)
async def get_logs(
    app_id: int,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    level: Optional[str] = Query(None, regex="^(DEBUG|INFO|WARNING|ERROR)$"),
    connection_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get logs for an app with filtering."""
    try:
        auth_service = AuthService(db)
        logs, total = await auth_service.get_logs(
            app_id=app_id,
            start_time=start_time,
            end_time=end_time,
            level=level,
            connection_id=connection_id,
            limit=limit,
            offset=offset
        )
        return BridgeLogList(total=total, logs=logs)
    except Exception as e:
        logger.error(f"Error retrieving logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 