from fastapi import APIRouter, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional, Dict
import json
import asyncio
from datetime import datetime

router = APIRouter()

# Store active bridge connections
bridge_connections: Dict[str, WebSocket] = {}

@router.websocket("/bridge/connect")
async def connect_bridge(
    websocket: WebSocket,
    api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    WebSocket endpoint for bridge clients.
    Handles the initial connection and ongoing communication.
    """
    if not api_key:
        await websocket.close(code=4001, reason="API key is required")
        return
    
    # TODO: Validate API key against database
    
    # Generate a unique connection ID
    connection_id = f"bridge-{len(bridge_connections) + 1}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        await websocket.accept()
        bridge_connections[connection_id] = websocket
        
        # Send initial connection success message
        await websocket.send_json({
            "type": "connection_established",
            "connection_id": connection_id,
            "message": "Bridge connected successfully"
        })
        
        # Send a test command
        await websocket.send_json({
            "type": "command",
            "command": "test",
            "args": ["Hello from MCP!"]
        })
        
        try:
            while True:
                # Wait for responses from the bridge client
                data = await websocket.receive_json()
                print(f"Received from bridge {connection_id}: {data}")
        except WebSocketDisconnect:
            print(f"Bridge {connection_id} disconnected")
        finally:
            bridge_connections.pop(connection_id, None)
    
    except Exception as e:
        print(f"Error in bridge connection {connection_id}: {str(e)}")
        if connection_id in bridge_connections:
            bridge_connections.pop(connection_id)
        await websocket.close(code=1011, reason=str(e)) 