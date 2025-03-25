from .base import MCPTool, MCPMethod, mcp_method
from .registry import ToolRegistry
import sys
import traceback

# Debug print
print("Loading MCP tools", file=sys.stderr)

# Import tools with explicit error handling
try:
    print("Importing MinimalTool", file=sys.stderr)
    from .minimal_tool import MinimalTool
    # Always register the MinimalTool first
    print("Registering MinimalTool", file=sys.stderr)
    ToolRegistry.register(MinimalTool)
    print("MinimalTool registered successfully", file=sys.stderr)
except Exception as e:
    print(f"ERROR: Failed to import or register MinimalTool: {e}", file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)

# Try to import and register SystemInfoTool, but handle errors gracefully
try:
    print("Importing SystemInfoTool", file=sys.stderr)
    from .system_info import SystemInfoTool
    print("Registering SystemInfoTool", file=sys.stderr)
    # Try to register SystemInfoTool but don't fail if it encounters issues
    ToolRegistry.register(SystemInfoTool)
    print("SystemInfoTool registered successfully", file=sys.stderr)
except ImportError as e:
    print(f"WARNING: Could not import SystemInfoTool. Missing dependency? {e}", file=sys.stderr)
except Exception as e:
    print(f"WARNING: Could not register SystemInfoTool: {e}", file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)

# Export all the tools
print(f"Registered tools: {list(ToolRegistry._tools.keys())}", file=sys.stderr)
__all__ = ['MCPTool', 'MCPMethod', 'mcp_method', 'ToolRegistry', 'MinimalTool']
try:
    # Only add SystemInfoTool to __all__ if it was successfully imported
    from .system_info import SystemInfoTool
    __all__.append('SystemInfoTool')
except ImportError:
    # Skip if not available
    pass 