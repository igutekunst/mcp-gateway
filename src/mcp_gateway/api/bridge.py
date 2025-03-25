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
import traceback
from pathlib import Path
from ..models.base import get_db, AsyncSessionLocal
from ..models.auth import AppID, APIKey
from ..services.auth import AuthService
from ..core.bridge import MCPBridge
from ..core.utils import get_logs_dir
from ..tools import ToolRegistry
from ..schemas.auth import BridgeLogBatchCreate, BridgeLogList, BridgeLogResponse
from ..api.admin_auth import get_session

# We don't need to define a prefix here as it's defined in main.py
router = APIRouter(tags=["bridge"])

# Configure logging with stderr output for debugging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # Prevent output to stdout
logger.setLevel(logging.DEBUG)

# Add stderr handler for debugging
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.DEBUG)
stderr_formatter = logging.Formatter('BRIDGE-API: %(asctime)s - %(levelname)s - %(message)s')
stderr_handler.setFormatter(stderr_formatter)
logger.addHandler(stderr_handler)

# Debug print to stderr
print("MCP Bridge API module loaded", file=sys.stderr)

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

@router.websocket("")
async def handle_root_websocket(websocket: WebSocket):
    """Handle WebSocket connection at the root path for easier connectivity"""
    print("Root WebSocket endpoint called - forwarding to main handler", file=sys.stderr)
    # Don't need to extract API key here as the main handler will do it
    await handle_websocket(websocket)

@router.websocket("/connect")
async def handle_websocket(
    websocket: WebSocket
):
    """Handle WebSocket connection for bridge"""
    print("========== CLAUDE WEBSOCKET DEBUGGING ==========", file=sys.stderr)
    # Fix the route access to avoid using .get() which isn't supported
    route_path = "unknown"
    if 'route' in websocket.scope and hasattr(websocket.scope['route'], 'path'):
        route_path = websocket.scope['route'].path
    print(f"FastAPI route pattern: {route_path}", file=sys.stderr)
    print(f"Client host: {websocket.client.host}:{websocket.client.port}", file=sys.stderr)
    print(f"Request URL: {websocket.url}", file=sys.stderr)
    print(f"WebSocket protocol: {websocket.scope.get('subprotocols', [])}", file=sys.stderr)
    print(f"WebSocket headers: {dict(websocket.headers)}", file=sys.stderr)
    print(f"WebSocket query params: {dict(websocket.query_params)}", file=sys.stderr)
    
    connection_id = None
    bridge = None
    try:
        print("New WebSocket connection attempt", file=sys.stderr)
        logger.info("New WebSocket connection attempt")
        await websocket.accept()
        print("WebSocket connection accepted", file=sys.stderr)
        logger.debug("WebSocket connection accepted")
        
        # Send a test message as soon as connected
        try:
            print("Sending test message after connection...", file=sys.stderr)
            await websocket.send_text(json.dumps({
                "type": "test",
                "message": "If you see this, websocket communication is working"
            }))
            print("Test message sent successfully", file=sys.stderr)
        except Exception as e:
            print(f"Failed to send test message: {str(e)}", file=sys.stderr)
        
        # Extract API key from query parameters or headers
        query_params = websocket.query_params
        headers = websocket.headers
        
        api_key = query_params.get("api_key") or headers.get("x-api-key")
        
        # Explicit debugging for API key extraction
        print(f"API key in query params: {query_params.get('api_key')}", file=sys.stderr)
        print(f"API key in x-api-key header: {headers.get('x-api-key')}", file=sys.stderr)
        print(f"API key in X-API-Key header: {headers.get('X-API-Key')}", file=sys.stderr)
        
        if not api_key:
            print("No API key provided in WebSocket connection", file=sys.stderr)
            logger.error("No API key provided in WebSocket connection")
            await websocket.close(code=4001, reason="API key required")
            return
        
        print(f"API key extracted: {api_key[:5]}...", file=sys.stderr)
        logger.debug(f"API key extracted: {api_key[:5]}...")
        
        # Validate API key
        try:
            print("Creating database session", file=sys.stderr)
            async with AsyncSessionLocal() as db:
                logger.debug("Creating database session")
                print("Creating auth service", file=sys.stderr)
                auth_service = AuthService(db)
                print("Validating API key", file=sys.stderr)
                logger.debug("Validating API key")
                app = await auth_service.get_app_by_api_key(api_key)
                if not app:
                    print("Invalid API key provided in WebSocket connection", file=sys.stderr)
                    logger.error("Invalid API key provided in WebSocket connection")
                    await websocket.close(code=4001, reason="Invalid API key")
                    return
                
                print(f"API key validated successfully for app ID: {app.id}", file=sys.stderr)
                logger.debug(f"API key validated successfully for app ID: {app.id}")
                connection_id = f"bridge-{len(bridge_connections) + 1}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                print(f"Generated connection_id: {connection_id}", file=sys.stderr)
                logger.info(f"Generated connection_id: {connection_id}")
                
                print(f"Creating MCPBridge instance for app {app.id}", file=sys.stderr)
                logger.debug("Creating MCPBridge instance")
                bridge = MCPBridge(websocket, connection_id, app.id, api_key)
                bridge_connections[connection_id] = bridge
                
                # Use bridge's response method consistently
                print("Sending connection established message", file=sys.stderr)
                logger.info("Sending connection established message")
                await websocket.send_text(json.dumps({
                    "jsonrpc": "2.0",
                    "id": "connection",
                    "result": {
                        "type": "connection_established",
                        "connection_id": connection_id,
                        "message": "Bridge connected successfully"
                    }
                }))
                print("Connection established message sent", file=sys.stderr)
        except Exception as e:
            print(f"Error in WebSocket API key validation: {str(e)}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            if connection_id and bridge:
                del bridge_connections[connection_id]
            await websocket.close(code=4003, reason=f"Authentication error: {str(e)}")
            return

        # Main message handling loop
        print("Entering main message handling loop", file=sys.stderr)
        while True:
            try:
                print("Waiting for next message...", file=sys.stderr)
                logger.debug("Waiting for next message...")
                message = await websocket.receive_json()
                print(f"Received WebSocket message: {json.dumps(message)[:200]}...", file=sys.stderr)
                logger.debug(f"Received WebSocket message: {message}")
                await bridge.handle_message(message)
                print("Message handled successfully", file=sys.stderr)
                logger.debug("Message handled successfully")
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for connection {connection_id}", file=sys.stderr)
                logger.info(f"WebSocket disconnected for connection {connection_id}")
                break
            except Exception as e:
                print(f"Error handling message: {str(e)}", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                logger.error(f"Error handling message: {str(e)}")
                continue
    except WebSocketDisconnect:
        print(f"Bridge {connection_id} disconnected", file=sys.stderr)
        logger.info(f"Bridge {connection_id} disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        if bridge:
            print("Cleaning up bridge resources", file=sys.stderr)
            logger.debug("Cleaning up bridge resources")
            await bridge.cleanup()
        if connection_id and connection_id in bridge_connections:
            print(f"Removing connection {connection_id} from active connections", file=sys.stderr)
            logger.debug(f"Removing connection {connection_id} from active connections")
            del bridge_connections[connection_id]
        print("WebSocket handler completed", file=sys.stderr)
        logger.info("WebSocket handler completed")

@router.post("/echo")
async def echo(
    request: Request,
    message: str = ""
):
    """Simple echo endpoint for testing"""
    logger.debug(f"Echo request: {message}")
    return {"echo": message}

@router.get("/debug")
async def debug_info(request: Request):
    """Return debugging information about the MCP server"""
    from ..tools.registry import ToolRegistry
    
    # Get the base URL from the request
    host = request.headers.get("host", "localhost:8000")
    scheme = request.headers.get("x-forwarded-proto", "http")
    base_url = f"{scheme}://{host}"
    
    # Get list of registered tools
    tools_info = ToolRegistry.get_capabilities()
    tool_names = list(tools_info.keys())
    
    return {
        "server_info": {
            "timestamp": datetime.utcnow().isoformat(),
            "base_url": base_url,
            "websocket_endpoints": [
                f"{base_url}/api/bridge",
                f"{base_url}/api/bridge/connect"
            ],
            "available_tools": tool_names,
            "tools_count": len(tool_names),
        },
        "connection_help": {
            "websocket_url": f"{base_url.replace('http', 'ws')}/api/bridge",
            "api_key_header": "X-API-Key: your_api_key_here",
            "initialize_message": {
                "jsonrpc": "2.0",
                "method": "initialize",
                "id": "1",
                "params": {
                    "capabilities": {}
                }
            }
        },
        "request_headers": dict(request.headers),
        "active_connections": len(bridge_connections)
    }

@router.post("/initialize")
async def http_initialize(request: Request):
    """Handle initialize request via HTTP for clients that don't support WebSockets"""
    print("HTTP initialize endpoint called", file=sys.stderr)
    
    try:
        # Get the request body
        body = await request.json()
        print(f"HTTP initialize request body: {json.dumps(body)}", file=sys.stderr)
        
        # Check if this is a proper initialize request
        if body.get("method") != "initialize" or body.get("jsonrpc") != "2.0":
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Invalid Request: Not an initialize request"
                },
                "id": body.get("id", "")
            }
        
        # Extract API key from headers
        api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
        print(f"HTTP initialize API key: {api_key[:5] if api_key else None}...", file=sys.stderr)
        
        if not api_key:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32001,
                    "message": "Unauthorized: API key required"
                },
                "id": body.get("id", "")
            }
        
        # Validate API key
        async with AsyncSessionLocal() as db:
            auth_service = AuthService(db)
            app = await auth_service.get_app_by_api_key(api_key)
            
            if not app:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized: Invalid API key"
                    },
                    "id": body.get("id", "")
                }
            
            print(f"HTTP initialize valid API key for app {app.id}", file=sys.stderr)
        
        # Get capabilities
        from ..tools.registry import ToolRegistry
        try:
            tools_capabilities = ToolRegistry.get_capabilities()
        except Exception as e:
            print(f"Error getting tool capabilities: {str(e)}", file=sys.stderr)
            tools_capabilities = {}
        
        # Return response
        response = {
            "jsonrpc": "2.0",
            "id": body.get("id", ""),
            "result": {
                "protocol": {
                    "version": "2024-11-05",
                    "capabilities": {
                        "tools": True,
                        "resources": False,
                        "prompts": False,
                        "sampling": False
                    }
                },
                "tools": tools_capabilities
            }
        }
        
        print("HTTP initialize sending response", file=sys.stderr)
        return response
    except Exception as e:
        print(f"HTTP initialize error: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": f"Internal error: {str(e)}"
            },
            "id": ""
        }

@router.post("/invoke")
async def http_method_call(request: Request):
    """Handle method calls via HTTP for clients that don't support WebSockets"""
    print("HTTP method call endpoint called", file=sys.stderr)
    
    try:
        # Get the request body
        body = await request.json()
        print(f"HTTP method call request body: {json.dumps(body)[:200]}...", file=sys.stderr)
        
        # Extract method, id, and params
        method = body.get("method")
        request_id = body.get("id", "")
        params = body.get("params", {})
        
        if not method or "." not in method:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600,
                    "message": "Invalid method format"
                },
                "id": request_id
            }
        
        # Extract API key
        api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
        print(f"HTTP method call API key: {api_key[:5] if api_key else None}...", file=sys.stderr)
        
        if not api_key:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32001,
                    "message": "Unauthorized: API key required"
                },
                "id": request_id
            }
        
        # Validate API key
        async with AsyncSessionLocal() as db:
            auth_service = AuthService(db)
            app = await auth_service.get_app_by_api_key(api_key)
            
            if not app:
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized: Invalid API key"
                    },
                    "id": request_id
                }
            
            print(f"HTTP method call valid API key for app {app.id}", file=sys.stderr)
        
        # Handle the method call
        tool_name, method_name = method.split(".", 1)
        
        from ..tools.registry import ToolRegistry
        tool = ToolRegistry.get_tool(tool_name)
        
        if not tool:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Tool '{tool_name}' not found"
                },
                "id": request_id
            }
            
        if method_name not in tool.methods:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method '{method_name}' not found"
                },
                "id": request_id
            }
        
        print(f"Executing method {method} with params {params}", file=sys.stderr)
        result = await tool.methods[method_name].handler(tool, **(params or {}))
        
        # Return response
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        
        print("HTTP method call sending response", file=sys.stderr)
        return response
    except Exception as e:
        print(f"HTTP method call error: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32000,
                "message": f"Internal error: {str(e)}"
            },
            "id": body.get("id", "") if 'body' in locals() else ""
        }

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

@router.get("")
async def bridge_root():
    """Root endpoint for the bridge API"""
    return {
        "service": "MCP Bridge API",
        "status": "running",
        "endpoints": {
            "debug": "/api/bridge/debug - Get debugging information",
            "echo": "/api/bridge/echo - Simple echo endpoint",
            "heartbeat": "/api/bridge/heartbeat - Send heartbeats",
            "logs": "/api/bridge/logs - Get/create logs",
            "websocket": "/api/bridge - WebSocket connection endpoint"
        },
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(bridge_connections)
    } 