from typing import Dict, Type, Optional
from .base import MCPTool

class ToolRegistry:
    """Registry for MCP tools"""
    _tools: Dict[str, MCPTool] = {}
    
    @classmethod
    def register(cls, tool_class: Type[MCPTool]) -> None:
        """Register a new tool"""
        tool = tool_class()
        cls._tools[tool.name] = tool
    
    @classmethod
    def get_tool(cls, name: str) -> Optional[MCPTool]:
        """Get a tool by name"""
        return cls._tools.get(name)
    
    @classmethod
    def get_capabilities(cls) -> Dict[str, Dict[str, any]]:
        """Get capabilities of all registered tools"""
        return {
            name: tool.get_capabilities()
            for name, tool in cls._tools.items()
        } 