from typing import Dict, Any
import platform
import datetime

from .base import MCPTool, mcp_method

class MinimalTool(MCPTool):
    """Simple tool for basic operations"""
    name = "minimal"
    description = "Provides basic functionality without external dependencies"
    version = "1.0.0"
    
    @mcp_method(
        description="Get current date and time",
        parameters={},
        returns={"type": "string", "description": "Current date and time"}
    )
    async def get_current_time(self) -> str:
        """Get the current date and time"""
        return datetime.datetime.now().isoformat()
    
    @mcp_method(
        description="Get platform information",
        parameters={},
        returns={"type": "object", "description": "Platform information"}
    )
    async def get_platform_info(self) -> Dict[str, Any]:
        """Get basic platform information"""
        return {
            "system": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version()
        }
    
    @mcp_method(
        description="Echo back the input",
        parameters={
            "text": {"type": "string", "description": "Text to echo"}
        },
        returns={"type": "string", "description": "The same text that was input"}
    )
    async def echo(self, text: str) -> str:
        """Echo back the input text"""
        return text 