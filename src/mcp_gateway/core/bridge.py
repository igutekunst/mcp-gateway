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
import traceback
from .logging import BridgeLogger
from .utils import get_logs_dir

# Configure logging to both file and stderr for debugging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # Prevent output to stdout
logger.setLevel(logging.DEBUG)

# Also add a stderr handler for debugging in Claude environment
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.DEBUG)
stderr_formatter = logging.Formatter('MCPBRIDGE: %(asctime)s - %(levelname)s - %(message)s')
stderr_handler.setFormatter(stderr_formatter)
logger.addHandler(stderr_handler)

# Debug print to stderr for immediate visibility
print("MCP Bridge module loaded", file=sys.stderr)

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
        print(f"Logging to {logs_dir / 'bridge.log'}", file=sys.stderr)
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
        
        # Remove error field if it's None to avoid validation errors in Claude
        if data["error"] is None:
            del data["error"]
            
        logger.debug(f"Response data after model_dump: {data}")
        return data

class MCPBridge:
    def __init__(self, websocket: WebSocket, connection_id: str, app_id: int, api_key: str):
        print(f"Creating MCPBridge: connection_id={connection_id}, app_id={app_id}", file=sys.stderr)
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
        print(f"MCPBridge initialized successfully for connection {connection_id}", file=sys.stderr)
        
    async def handle_message(self, message: dict) -> None:
        """Handle incoming MCP message"""
        # Track if we've sent a response to avoid duplicates
        response_sent = False
        
        try:
            print(f"Handling raw message: {json.dumps(message)[:200]}...", file=sys.stderr)
            
            # Special handling for initialize message
            if isinstance(message, dict) and message.get("method") == "initialize" and message.get("jsonrpc") == "2.0":
                print(f"Detected initialize message directly: {json.dumps(message)}", file=sys.stderr)
                try:
                    # Try to quickly handle the initialize request directly
                    print("Attempting quick initialize response", file=sys.stderr)
                    quick_response = {
                        "jsonrpc": "2.0",
                        "id": message.get("id", "0"),
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
                            "tools": {
                                "minimal": {
                                    "name": "minimal",
                                    "description": "Minimal tool that echoes text",
                                    "version": "1.0.0",
                                    "methods": {
                                        "echo": {
                                            "name": "echo",
                                            "description": "Echo back the input",
                                            "parameters": {
                                                "text": {
                                                    "type": "string",
                                                    "description": "Text to echo"
                                                }
                                            },
                                            "returns": {
                                                "type": "string",
                                                "description": "The same text that was input"
                                            },
                                            "is_async": True
                                        }
                                    }
                                }
                            }
                        }
                    }
                    
                    print(f"Sending quick initialize response with ID: {message.get('id', '0')}", file=sys.stderr)
                    await self.websocket.send_json(quick_response)
                    print("Quick initialize response sent successfully", file=sys.stderr)
                    self.initialized = True
                    response_sent = True
                    return
                except Exception as e:
                    print(f"Quick initialize response failed: {str(e)}", file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    # Fall back to regular initialization flow
            
            # Normal message handling
            request = MCPRequest(**message)
            self.logger.debug("Received message", {
                "request_id": request.id,
                "method": request.method,
                "has_params": request.params is not None
            })
        except Exception as e:
            print(f"Error parsing message: {str(e)}", file=sys.stderr)
            print(f"Message was: {message}", file=sys.stderr)
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
        
        # Skip normal handling if we've already sent a response
        if response_sent:
            print(f"Response already sent for message, skipping normal flow", file=sys.stderr)
            return

        if request.method == "initialize":
            print(f"Initialize request received with id {request.id}", file=sys.stderr)
            self.logger.info("Handling initialize request", {
                "request_id": request.id
            })
            await self._handle_initialize(request)
        elif not self.initialized:
            print(f"Received request {request.method} before initialization", file=sys.stderr)
            self.logger.warning("Received request before initialization", {
                "request_id": request.id,
                "method": request.method
            })
            await self._send_error(-32002, "Server not initialized", request.id)
        else:
            print(f"Handling method call: {request.method}", file=sys.stderr)
            await self._handle_method_call(request)

    async def _handle_initialize(self, request: MCPRequest) -> None:
        """Handle initialize request"""
        try:
            print(f"Beginning initialize for request ID: {request.id}", file=sys.stderr)
            # Initialize request should not have any parameters
            if request.params:
                print(f"Initialize has unexpected params: {request.params}", file=sys.stderr)
                self.logger.warning("Initialize request contained params", {
                    "request_id": request.id,
                    "params": request.params
                })
                await self._send_error(-32602, "Invalid params: initialize request does not accept parameters", request.id)
                return

            if self.initialized:
                print(f"Already initialized for request ID: {request.id}", file=sys.stderr)
                self.logger.warning("Received initialize request when already initialized", {
                    "request_id": request.id
                })
                await self._send_error(-32002, "Server already initialized", request.id)
                return

            print(f"Setting initialized=True for request ID: {request.id}", file=sys.stderr)
            self.logger.info("Initializing bridge", {
                "request_id": request.id
            })
            self.client_capabilities = {}
            self.initialized = True
            
            # Send server capabilities
            print("Importing ToolRegistry", file=sys.stderr)
            from ..tools.registry import ToolRegistry
            
            print("Getting tool capabilities", file=sys.stderr)
            try:
                tools_capabilities = ToolRegistry.get_capabilities()
                print(f"Got capabilities for {len(tools_capabilities)} tools", file=sys.stderr)
                for tool_name in tools_capabilities:
                    print(f"Registered tool: {tool_name}", file=sys.stderr)
            except Exception as e:
                print(f"Error getting tool capabilities: {str(e)}", file=sys.stderr)
                tools_capabilities = {}  # Fallback to empty capabilities
            
            print("Creating capabilities response", file=sys.stderr)
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
                "tools": tools_capabilities
            }
            
            print(f"Sending response for initialize request ID: {request.id}", file=sys.stderr)
            await self._send_response(capabilities_response, request.id)
            print(f"Initialize completed for request ID: {request.id}", file=sys.stderr)
            self.logger.info("Initialize completed successfully")
        except Exception as e:
            print(f"Error in _handle_initialize: {str(e)}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            self.logger.error(f"Initialize error: {str(e)}")
            await self._send_error(-32000, f"Internal error: {str(e)}", request.id)

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

    async def _send_response(self, result: Dict[str, Any], request_id: str) -> None:
        """Send successful response"""
        try:
            print(f"Building response for request ID: {request_id}", file=sys.stderr)
            response = MCPResponse(id=request_id, result=result, error=None)
            response_dict = response.model_dump()
            print(f"Response dict: {json.dumps(response_dict)[:200]}...", file=sys.stderr)
            
            await self.websocket.send_json(response_dict)
            print(f"Response sent successfully for request ID: {request_id}", file=sys.stderr)
        except Exception as e:
            print(f"Error sending response: {str(e)}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            self.logger.error("Failed to send response", {
                "request_id": request_id,
                "error": str(e)
            })

    async def _send_error(self, code: int, message: str, request_id: str) -> None:
        """Send error response"""
        try:
            error = {
                "code": code,
                "message": message
            }
            
            print(f"Sending error response for request ID {request_id}: {code} - {message}", file=sys.stderr)
            response = MCPResponse(id=request_id, result=None, error=error)
            response_dict = response.model_dump()
            
            # For error responses, result should be null, not absent
            if "result" not in response_dict:
                response_dict["result"] = None
            
            print(f"Error response dict: {json.dumps(response_dict)}", file=sys.stderr)
            
            await self.websocket.send_json(response_dict)
            print(f"Error response sent successfully for request ID: {request_id}", file=sys.stderr)
        except Exception as e:
            print(f"Error sending error response: {str(e)}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
            self.logger.error("Failed to send error response", {
                "request_id": request_id,
                "error_code": code,
                "error_message": message,
                "exception": str(e)
            })

    def update_heartbeat(self) -> None:
        """Update the last heartbeat time"""
        self.last_heartbeat = datetime.utcnow()
        self.logger.debug("Updated heartbeat")

    async def cleanup(self) -> None:
        """Clean up resources when bridge is disconnected"""
        await self.logger.stop()
        self.logger.info("Bridge disconnected") 