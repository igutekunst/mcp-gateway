from typing import Any, Dict, List, Optional, Type, Callable
from pydantic import BaseModel, Field
import inspect
import asyncio
from functools import wraps

class MCPMethod(BaseModel):
    """Represents a method in an MCP tool"""
    name: str
    description: str
    parameters: Dict[str, Any]
    returns: Dict[str, Any]
    is_async: bool = False

class MCPTool:
    """Base class for all MCP tools"""
    name: str
    description: str
    version: str = "1.0.0"
    methods: Dict[str, MCPMethod] = {}
    
    def __init__(self):
        self._register_methods()
    
    def _register_methods(self):
        """Register all methods in the tool"""
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if hasattr(method, '_mcp_method'):
                self.methods[name] = method._mcp_method
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get tool capabilities including methods"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "methods": {
                name: method.dict()
                for name, method in self.methods.items()
            }
        }

def mcp_method(
    description: str,
    parameters: Optional[Dict[str, Any]] = None,
    returns: Optional[Dict[str, Any]] = None
):
    """Decorator to mark a method as an MCP method"""
    def decorator(func: Callable):
        # Get parameter annotations
        sig = inspect.signature(func)
        param_annotations = {
            name: param.annotation
            for name, param in sig.parameters.items()
            if param.annotation != inspect.Parameter.empty
        }
        
        # Create MCPMethod instance
        method = MCPMethod(
            name=func.__name__,
            description=description,
            parameters=parameters or param_annotations,
            returns=returns or {"type": "any"},
            is_async=inspect.iscoroutinefunction(func)
        )
        
        # Attach to function
        func._mcp_method = method
        
        # Preserve original function
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    return decorator 