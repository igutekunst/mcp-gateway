from typing import Dict, Optional, Any
from pydantic import BaseModel, ConfigDict
import json
from fastapi import WebSocket
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: str  # Make id required

class MCPResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    jsonrpc: str = "2.0"
    id: str  # Make id required
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:
        data = super().model_dump(*args, **kwargs)
        data["id"] = str(data["id"])  # Ensure id is a string
        logger.debug(f"Response data after model_dump: {data}")
        return data

class MCPBridge:
    def __init__(self, websocket: WebSocket, connection_id: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.initialized = False
        self.client_capabilities = {}
        self.last_heartbeat = datetime.utcnow()
        logger.info(f"Created new MCPBridge with connection_id: {connection_id}")
        
    async def handle_message(self, message: dict) -> None:
        """Handle incoming MCP message"""
        logger.info(f"Received message: {message}")
        try:
            request = MCPRequest(**message)
            logger.debug(f"Parsed request: {request}")
        except Exception as e:
            logger.error(f"Failed to parse message: {e}")
            await self._send_error(
                request_id="",
                code=-32600,
                message="Invalid Request"
            )
            return

        if request.method == "initialize":
            logger.info(f"Handling initialize request with id: {request.id}")
            await self._handle_initialize(request)
        elif not self.initialized:
            logger.warning(f"Received request {request.method} before initialization")
            await self._send_error(-32002, "Server not initialized", request.id)
        else:
            await self._handle_method_call(request)

    async def _handle_initialize(self, request: MCPRequest) -> None:
        """Handle initialize request"""
        # Initialize request should not have any parameters
        if request.params:
            logger.warning(f"Initialize request contained params: {request.params}")
            await self._send_error(-32602, "Invalid params: initialize request does not accept parameters", request.id)
            return

        if self.initialized:
            logger.warning(f"Received initialize request when already initialized")
            await self._send_error(-32002, "Server already initialized", request.id)
            return

        logger.info(f"Initializing bridge with request id: {request.id}")
        self.client_capabilities = {}
        self.initialized = True
        
        # Send server capabilities
        from ..tools.registry import ToolRegistry
        capabilities_response = {
            "protocol": {
                "version": "2024-11-05",
                "capabilities": {
                    "tools": True,
                    "resources": False,
                    "prompts": False,
                    "sampling": False
                }
            },
            "tools": ToolRegistry.get_capabilities()
        }
        logger.debug(f"Sending capabilities response with id: {request.id}")
        await self._send_response(capabilities_response, request.id)

    async def _handle_method_call(self, request: MCPRequest) -> None:
        """Handle tool method calls"""
        try:
            if "." not in request.method:
                await self._send_error(-32601, f"Method '{request.method}' not found", request.id)
                return
                
            tool_name, method_name = request.method.split(".", 1)
            
            from ..tools.registry import ToolRegistry
            tool = ToolRegistry.get_tool(tool_name)
            
            if not tool:
                await self._send_error(-32601, f"Tool '{tool_name}' not found", request.id)
                return
                
            if method_name not in tool.methods:
                await self._send_error(-32601, f"Method '{method_name}' not found", request.id)
                return

            result = await tool.methods[method_name].handler(tool, **(request.params or {}))
            await self._send_response(result, request.id)
            
        except Exception as e:
            await self._send_error(-32000, str(e), request.id)

    async def _send_response(self, result: Dict[str, Any], request_id: Optional[str] = None) -> None:
        """Send a JSON-RPC response"""
        logger.info(f"Preparing response for request_id: {request_id}")
        if request_id is None:
            logger.warning("request_id is None, using empty string")
        response = MCPResponse(
            result=result,
            id=request_id or ""  # Convert None to empty string at creation time
        )
        response_data = response.model_dump()
        logger.debug(f"Sending response: {response_data}")
        await self.websocket.send_json(response_data)

    async def _send_error(self, code: int, message: str, request_id: Optional[str] = None) -> None:
        """Send a JSON-RPC error response"""
        response = MCPResponse(
            error={
                "code": code,
                "message": message
            },
            id=request_id or ""  # Convert None to empty string at creation time
        )
        await self.websocket.send_json(response.model_dump())

    def update_heartbeat(self) -> None:
        """Update the last heartbeat time"""
        self.last_heartbeat = datetime.utcnow() 