import os
from pathlib import Path
import platform
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

def get_xdg_data_home() -> Path:
    """Get XDG_DATA_HOME path, creating if necessary."""
    if platform.system().lower() == "darwin":
        base_path = Path.home() / "Library/Application Support"
    elif platform.system().lower() == "windows":
        base_path = Path(os.getenv("APPDATA", str(Path.home() / "AppData/Roaming")))
    else:  # Linux and others - XDG standard
        base_path = Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    
    return base_path / "mcp-gateway"

def get_xdg_config_home() -> Path:
    """Get XDG_CONFIG_HOME path, creating if necessary."""
    if platform.system().lower() == "darwin":
        base_path = Path.home() / "Library/Application Support"
    elif platform.system().lower() == "windows":
        base_path = Path(os.getenv("APPDATA", str(Path.home() / "AppData/Roaming")))
    else:  # Linux and others - XDG standard
        base_path = Path(os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    
    return base_path / "mcp-gateway"

def get_xdg_cache_home() -> Path:
    """Get XDG_CACHE_HOME path, creating if necessary."""
    if platform.system().lower() == "darwin":
        base_path = Path.home() / "Library/Caches"
    elif platform.system().lower() == "windows":
        base_path = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    else:  # Linux and others - XDG standard
        base_path = Path(os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    
    return base_path / "mcp-gateway"

# Ensure directories exist
data_dir = get_xdg_data_home()
config_dir = get_xdg_config_home()
cache_dir = get_xdg_cache_home()

for directory in (data_dir, config_dir, cache_dir):
    directory.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite+aiosqlite:///{data_dir}/mcp-gateway.db"

engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session 