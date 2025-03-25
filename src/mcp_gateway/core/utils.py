import os
import sys
import platform
from pathlib import Path
from typing import Optional

def get_logs_dir() -> Optional[Path]:
    """Get platform-specific logs directory following XDG Base Directory Specification."""
    if platform.system() == "Windows":
        base_dir = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        log_dir = Path(base_dir) / "mcp-gateway" / "logs"
    elif platform.system() == "Darwin":  # macOS
        log_dir = Path.home() / "Library" / "Logs" / "mcp-gateway"
    else:  # Linux and other Unix-like systems
        xdg_cache_home = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
        log_dir = Path(xdg_cache_home) / "mcp-gateway" / "logs"
    
    # Create directory if it doesn't exist
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, IOError) as e:
        # Fall back to stderr if we can't create log directory
        print(f"Warning: Could not create log directory {log_dir}: {e}", file=sys.stderr)
        return None
    
    return log_dir 