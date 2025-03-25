from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json
from typing import Dict, Optional, List, Any, Union
import uuid
import logging
import os
import platform
import sys
from pathlib import Path
from ..models.base import get_db, AsyncSessionLocal
from ..models.auth import AppID, APIKey
from ..services.auth import AuthService
from ..core.bridge import MCPBridge
from ..core.utils import get_logs_dir
from ..tools import ToolRegistry
from ..schemas.auth import BridgeLogBatchCreate, BridgeLogList, BridgeLogResponse
from ..api.admin_auth import get_session

router = APIRouter()

# Configure logging to only write to file
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # Prevent output to stdout
logger.setLevel(logging.DEBUG)

# Get logs directory from core.utils
logs_dir = get_logs_dir()
if logs_dir:
    try:
        # Add file handler for bridge API logs
        file_handler = logging.FileHandler(str(logs_dir / "bridge_api.log"))
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.debug("Bridge API logging initialized to " + str(logs_dir))
    except (OSError, IOError) as e:
        print(f"Warning: Could not set up file logging for bridge API: {e}", file=sys.stderr)

# Store active bridge connections
bridge_connections: Dict[str, MCPBridge] = {}

@router.post("/heartbeat")
async def bridge_heartbeat(
    request: dict,
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle bridge heartbeat"""
    try:
        # Extract API key directly from headers
        api_key = req.headers.get("x-api-key") or req.headers.get("X-API-Key")
        logger.debug(f"Heartbeat received with API key: {api_key}")
        
        # Also check API key in body for backward compatibility
        body_api_key = None
        if isinstance(request, dict) and "api_key" in request:
            body_api_key = request.get("api_key")
            logger.debug(f"Found body API key: {body_api_key}")
        
        # Use any available API key
        actual_api_key = api_key or body_api_key
        
        auth_service = AuthService(db)
        app = None
        
        # Try API key authentication
        if actual_api_key:
            app = await auth_service.get_app_by_api_key(actual_api_key)
            if app:
                logger.debug(f"API key authentication successful for app: {app.id}")
                # Update app's last_connected timestamp
                app.last_connected = datetime.utcnow()
                await db.commit()
                
                return {
                    "status": "ok",
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                logger.warning(f"Invalid API key: {actual_api_key}")
        
        # Fallback to session authentication
        authenticated, _ = get_session(req)
        if authenticated:
            logger.debug("Session authentication successful")
            return {
                "status": "ok",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # If we get here, authentication failed
        logger.warning("Authentication failed for heartbeat")
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    except Exception as e:
        logger.error(f"Heartbeat error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/connect")
async def handle_websocket(
    websocket: WebSocket
):
    """Handle WebSocket connection for bridge"""
    connection_id = None
    bridge = None
    try:
        logger.info("New WebSocket connection attempt")
        await websocket.accept()
        
        # Extract API key from query parameters or headers
        query_params = websocket.query_params
        headers = websocket.headers
        
        api_key = query_params.get("api_key") or headers.get("x-api-key")
        if not api_key:
            logger.error("No API key provided in WebSocket connection")
            await websocket.close(code=4001, reason="API key required")
            return
        
        # Validate API key
        async with AsyncSessionLocal() as db:
            auth_service = AuthService(db)
            app = await auth_service.get_app_by_api_key(api_key)
            if not app:
                logger.error("Invalid API key provided in WebSocket connection")
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
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Create multiple log entries."""
    try:
        # Extract API key directly from headers
        api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
        logger.debug(f"Log creation request with API key: {api_key}")
        
        auth_service = AuthService(db)
        app = None
        
        # Try API key authentication
        if api_key:
            app = await auth_service.get_app_by_api_key(api_key)
            if not app:
                logger.warning(f"Invalid API key: {api_key}")
                raise HTTPException(status_code=401, detail="Invalid API key")
        else:
            # Check session authentication
            authenticated, _ = get_session(request)
            if not authenticated:
                logger.warning("No valid authentication for log creation")
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            # For admin session, we need to get the app from the logs
            if not logs.logs:
                raise HTTPException(status_code=400, detail="No logs provided")
            
            # For session auth, each log must have app_id
            for log in logs.logs:
                if not hasattr(log, 'app_id'):
                    raise HTTPException(status_code=400, detail="App ID must be provided in each log when using session authentication")
            
            # Get the app by ID from the first log
            app_id = logs.logs[0].app_id
            app = await auth_service.get_app_by_id(str(app_id))
            if not app:
                raise HTTPException(status_code=404, detail=f"App with ID {app_id} not found")
        
        logger.debug(f"Creating logs for app {app.id}")
        created_logs = await auth_service.create_logs(app.id, logs)
        return created_logs
    except Exception as e:
        logger.error(f"Error creating logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/{app_id}", response_model=BridgeLogList)
async def get_logs(
    app_id: int,
    request: Request,
    level: Optional[str] = Query(None, pattern="^(DEBUG|INFO|WARNING|ERROR)$"),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get logs for an app with filtering."""
    try:
        # Extract API key directly from headers
        api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
        logger.debug(f"Log retrieval request for app {app_id} with API key: {api_key}")
        
        auth_service = AuthService(db)
        
        # Try API key authentication
        if api_key:
            app = await auth_service.get_app_by_api_key(api_key)
            if not app:
                logger.warning(f"Invalid API key: {api_key}")
                raise HTTPException(status_code=401, detail="Invalid API key")
            
            # Verify if the API key has access to this app's logs
            if app.id != app_id:
                logger.warning(f"API key associated with app {app.id} attempted to access logs for app {app_id}")
                raise HTTPException(status_code=403, detail="You don't have permission to access these logs")
        else:
            # Check session authentication for admin access
            authenticated, _ = get_session(request)
            if not authenticated:
                logger.warning("No valid authentication for log retrieval")
                raise HTTPException(status_code=401, detail="Unauthorized")
            
            # Admin can access any app's logs
            logger.debug(f"Admin session accessing logs for app {app_id}")
        
        logger.debug(f"Retrieving logs for app {app_id}")
        logs, total = await auth_service.get_logs(
            app_id=app_id,
            start_time=start_time,
            end_time=end_time,
            level=level,
            limit=limit,
            offset=offset
        )
        return BridgeLogList(total=total, logs=logs)
    except Exception as e:
        logger.error(f"Error retrieving logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 