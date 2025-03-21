from datetime import datetime
from typing import List, Optional, Dict, Any
import psutil
from pydantic import BaseModel

from .base import MCPTool, mcp_method

class MemoryInfo(BaseModel):
    total: int
    available: int
    percent: float
    used: int

class ProcessInfo(BaseModel):
    pid: int
    name: str
    memory_mb: float
    cpu_percent: float
    status: str
    create_time: float

class ProcessFilter(BaseModel):
    name_contains: Optional[str] = None
    min_memory_mb: Optional[float] = None
    min_cpu_percent: Optional[float] = None

class SystemInfoTool(MCPTool):
    """Tool for getting system information"""
    name = "system_info"
    description = "Get system information like CPU usage, memory, etc."
    version = "1.0.0"
    
    @mcp_method(
        description="Get current CPU usage percentage",
        parameters={},
        returns={"type": "number", "description": "CPU usage percentage"}
    )
    async def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage"""
        return psutil.cpu_percent()

    @mcp_method(
        description="Get memory usage information",
        parameters={},
        returns={"type": "object", "description": "Memory usage information"}
    )
    async def get_memory_info(self) -> MemoryInfo:
        """Get detailed memory usage information"""
        mem = psutil.virtual_memory()
        return MemoryInfo(
            total=mem.total,
            available=mem.available,
            percent=mem.percent,
            used=mem.used
        )

    @mcp_method(
        description="List running processes with optional filtering",
        parameters={
            "filter": {
                "type": "object",
                "description": "Optional filter criteria for processes",
                "properties": {
                    "name_contains": {"type": "string", "description": "Filter by process name"},
                    "min_memory_mb": {"type": "number", "description": "Minimum memory usage in MB"},
                    "min_cpu_percent": {"type": "number", "description": "Minimum CPU usage percentage"}
                }
            }
        },
        returns={"type": "array", "description": "List of process information"}
    )
    async def list_processes(self, filter: Optional[ProcessFilter] = None) -> List[ProcessInfo]:
        """List running processes with optional filtering"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'status', 'create_time']):
            try:
                info = proc.info
                memory_mb = info['memory_info'].rss / 1024 / 1024
                
                # Apply filters if provided
                if filter:
                    if (filter.name_contains and filter.name_contains.lower() not in info['name'].lower()) or \
                       (filter.min_memory_mb and memory_mb < filter.min_memory_mb) or \
                       (filter.min_cpu_percent and info['cpu_percent'] < filter.min_cpu_percent):
                        continue
                
                processes.append(ProcessInfo(
                    pid=info['pid'],
                    name=info['name'],
                    memory_mb=memory_mb,
                    cpu_percent=info['cpu_percent'],
                    status=info['status'],
                    create_time=info['create_time']
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return processes 