import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class MCPError(Exception):
    """Base class for MCP protocol errors."""
    def __init__(self, code: int, message: str, data: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

class InvalidParamsError(MCPError):
    def __init__(self, message: str, data: Optional[Dict[str, Any]] = None):
        super().__init__(-32602, f"Invalid params: {message}", data)

class MCPServer:
    """Core MCP protocol implementation."""
    
    def __init__(self):
        self.capabilities = {
            "tools": {
                "supported": True,
                "canInvoke": True
            },
            "prompts": {
                "supported": False
            },
            "resources": {
                "supported": True,
                "canRead": True,
                "canWrite": False
            },
            "logging": {
                "supported": False
            },
            "roots": {
                "listChanged": False
            }
        }
        self.initialized = False
        self.tools = {
            "mcp_mcp_gateway_test_echo": {
                "name": "mcp_mcp_gateway_test_echo",
                "title": "Echo Test Tool",
                "description": "A simple test tool that echoes back the input",
                "type": "function",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "Message to echo back"
                        }
                    },
                    "required": ["message"]
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["success"]
                        },
                        "content": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["text"]
                                    },
                                    "text": {
                                        "type": "string"
                                    }
                                },
                                "required": ["type", "text"]
                            }
                        }
                    },
                    "required": ["type", "content"]
                }
            }
        }

    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request from client."""
        logger.info("Handling initialize request")
        self.initialized = True
        return {
            "type": "success",
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "mcp-gateway",
                "version": "0.1.0"
            },
            "capabilities": self.capabilities
        }

    async def handle_initialized(self, params: Dict[str, Any]) -> None:
        """Handle initialized notification from client."""
        logger.info("Received initialized notification")
        # This is a notification, no response needed
        return None

    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Handle tools/list request."""
        logger.info("Handling tools/list request")
        return {"tools": list(self.tools.values())}

    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request according to MCP specification."""
        logger.info(f"Handling tools/call request with params: {params}")
        
        # Validate required fields according to MCP spec
        if not isinstance(params, dict):
            raise InvalidParamsError("params must be an object")
            
        # Extract tool name
        tool_name = params.get("name")
        if not tool_name:
            raise InvalidParamsError("missing required parameter 'name'")

        # Validate tool exists
        tool = self.tools.get(tool_name)
        if not tool:
            raise InvalidParamsError(f"unknown tool '{tool_name}'")

        # Extract arguments according to MCP spec
        arguments = params.get("arguments")
        if arguments is None:
            raise InvalidParamsError("missing required parameter 'arguments'")
            
        logger.debug(f"Tool '{tool_name}' called with arguments: {arguments}")
        
        # Handle test_echo tool
        if tool_name == "mcp_mcp_gateway_test_echo":
            message = arguments.get("message")
            if message is None:
                raise InvalidParamsError("missing required argument 'message'")
                
            logger.debug(f"Echoing message: {message}")
            return {
                "type": "success",
                "content": [
                    {
                        "type": "text",
                        "text": message
                    }
                ]
            }

        raise InvalidParamsError(f"tool '{tool_name}' not implemented")

    def register_tool(self, name: str, tool: Dict[str, Any]) -> None:
        """Register a new tool with the server."""
        self.tools[name] = tool 