from typing import Dict, Optional, Any, List
from pydantic import BaseModel, ConfigDict
import json
from fastapi import WebSocket
from datetime import datetime
import logging
import os
import platform
from pathlib import Path
import sys
import asyncio
from .logging import BridgeLogger
from .utils import get_logs_dir

# Configure logging to only write to file
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # Prevent output to stdout
logger.setLevel(logging.DEBUG)

# Set up logging to file
logs_dir = get_logs_dir()
if logs_dir:
    # Add file handler for bridge logs
    try:
        file_handler = logging.FileHandler(str(logs_dir / "bridge.log"))
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except (OSError, IOError) as e:
        print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)

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
    def __init__(self, websocket: WebSocket, connection_id: str, app_id: int, api_key: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.app_id = app_id
        self.initialized = False
        self.client_capabilities = {}
        self.last_heartbeat = datetime.utcnow()
        
        # Initialize logger
        self.logger = BridgeLogger(
            app_id=app_id,
            connection_id=connection_id,
            api_key=api_key
        )
        self.logger.start()
        self.logger.info("Created new MCPBridge", {
            "app_id": app_id,
            "connection_id": connection_id
        })
        
    async def handle_message(self, message: dict) -> None:
        """Handle incoming MCP message"""
        try:
            request = MCPRequest(**message)
            self.logger.debug("Received message", {
                "request_id": request.id,
                "method": request.method,
                "has_params": request.params is not None
            })
        except Exception as e:
            self.logger.error("Failed to parse message", {
                "error": str(e),
                "raw_message": message
            })
            await self._send_error(
                request_id="",
                code=-32600,
                message="Invalid Request"
            )
            return

        if request.method == "initialize":
            self.logger.info("Handling initialize request", {
                "request_id": request.id
            })
            await self._handle_initialize(request)
        elif not self.initialized:
            self.logger.warning("Received request before initialization", {
                "request_id": request.id,
                "method": request.method
            })
            await self._send_error(-32002, "Server not initialized", request.id)
        else:
            await self._handle_method_call(request)

    async def _handle_initialize(self, request: MCPRequest) -> None:
        """Handle initialize request"""
        # Initialize request should not have any parameters
        if request.params:
            self.logger.warning("Initialize request contained params", {
                "request_id": request.id,
                "params": request.params
            })
            await self._send_error(-32602, "Invalid params: initialize request does not accept parameters", request.id)
            return

        if self.initialized:
            self.logger.warning("Received initialize request when already initialized", {
                "request_id": request.id
            })
            await self._send_error(-32002, "Server already initialized", request.id)
            return

        self.logger.info("Initializing bridge", {
            "request_id": request.id
        })
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
        await self._send_response(capabilities_response, request.id)

    async def _handle_method_call(self, request: MCPRequest) -> None:
        """Handle tool method calls"""
        try:
            if "." not in request.method:
                self.logger.error("Invalid method format", {
                    "request_id": request.id,
                    "method": request.method
                })
                await self._send_error(-32601, f"Method '{request.method}' not found", request.id)
                return
                
            tool_name, method_name = request.method.split(".", 1)
            
            from ..tools.registry import ToolRegistry
            tool = ToolRegistry.get_tool(tool_name)
            
            if not tool:
                self.logger.error("Tool not found", {
                    "request_id": request.id,
                    "tool_name": tool_name
                })
                await self._send_error(-32601, f"Tool '{tool_name}' not found", request.id)
                return
                
            if method_name not in tool.methods:
                self.logger.error("Method not found", {
                    "request_id": request.id,
                    "tool_name": tool_name,
                    "method_name": method_name
                })
                await self._send_error(-32601, f"Method '{method_name}' not found", request.id)
                return

            self.logger.info("Executing method", {
                "request_id": request.id,
                "tool_name": tool_name,
                "method_name": method_name,
                "has_params": request.params is not None
            })
            result = await tool.methods[method_name].handler(tool, **(request.params or {}))
            await self._send_response(result, request.id)
            
        except Exception as e:
            self.logger.error("Error handling method call", {
                "request_id": request.id,
                "error": str(e)
            })
            await self._send_error(-32000, str(e), request.id)

    async def _send_response(self, result: Dict[str, Any], request_id: Optional[str] = None) -> None:
        """Send a JSON-RPC response"""
        if request_id is None:
            self.logger.warning("request_id is None, using empty string")
        response = MCPResponse(
            result=result,
            id=request_id or ""
        )
        response_data = response.model_dump()
        self.logger.debug("Sending response", {
            "request_id": request_id,
            "response_type": "success"
        })
        await self.websocket.send_json(response_data)

    async def _send_error(self, code: int, message: str, request_id: Optional[str] = None) -> None:
        """Send a JSON-RPC error response"""
        response = MCPResponse(
            error={
                "code": code,
                "message": message
            },
            id=request_id or ""
        )
        self.logger.debug("Sending error response", {
            "request_id": request_id,
            "error_code": code,
            "error_message": message
        })
        await self.websocket.send_json(response.model_dump())

    def update_heartbeat(self) -> None:
        """Update the last heartbeat time"""
        self.last_heartbeat = datetime.utcnow()
        self.logger.debug("Updated heartbeat")

    async def cleanup(self) -> None:
        """Clean up resources when bridge is disconnected"""
        await self.logger.stop()
        self.logger.info("Bridge disconnected") 