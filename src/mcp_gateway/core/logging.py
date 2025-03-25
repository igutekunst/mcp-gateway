import asyncio
import logging
import httpx
from datetime import datetime, UTC
from typing import List, Dict, Any, Optional
import json
import sys
from pathlib import Path
from ..schemas.auth import BridgeLogCreate, BridgeLogBatchCreate
from fastapi.testclient import TestClient
from .utils import get_logs_dir

logger = logging.getLogger(__name__)

class BridgeLogger:
    """Logger for MCP bridge that supports both file and API logging with batching."""
    
    def __init__(
        self,
        app_id: int,
        connection_id: str,
        api_key: str,
        api_url: str = "http://localhost:8000",
        buffer_size: int = 100,
        flush_interval: float = 5.0,
        max_retries: int = 3,
        test_client: Optional[TestClient] = None
    ):
        self.app_id = app_id
        self.connection_id = connection_id
        self.api_key = api_key
        self.api_url = api_url.rstrip("/")
        self.buffer: List[BridgeLogCreate] = []
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.max_retries = max_retries
        self.flush_task: Optional[asyncio.Task] = None
        self.test_client = test_client
        self._setup_file_logging()
        
    def _setup_file_logging(self):
        """Set up file-based logging as fallback."""
        self.file_logger = logging.getLogger(f"bridge.{self.connection_id}")
        if not self.file_logger.handlers:
            logs_dir = get_logs_dir()
            
            if logs_dir:
                try:
                    # Create connection-specific log file
                    log_file = logs_dir / f"bridge_{self.connection_id}.log"
                    handler = logging.FileHandler(str(log_file))
                    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                    handler.setFormatter(formatter)
                    self.file_logger.addHandler(handler)
                    self.file_logger.setLevel(logging.DEBUG)
                    self.file_logger.debug(f"Bridge logger initialized at {log_file}")
                except (OSError, IOError) as e:
                    # Fall back to memory-only logging if file logging fails
                    print(f"Warning: Failed to set up file logging for bridge: {e}", file=sys.stderr)
                    self.file_logger.addHandler(logging.NullHandler())
            else:
                # No logs directory available, use null handler
                self.file_logger.addHandler(logging.NullHandler())
    
    def start(self):
        """Start the periodic flush task."""
        if self.flush_task is None or self.flush_task.done():
            self.flush_task = asyncio.create_task(self._periodic_flush())
    
    async def stop(self):
        """Stop the logger and flush remaining logs."""
        if self.flush_task and not self.flush_task.done():
            self.flush_task.cancel()
            try:
                await self.flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()
    
    def log(
        self,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a log entry to the buffer."""
        log_entry = BridgeLogCreate(
            level=level.upper(),
            message=message,
            connection_id=self.connection_id,
            timestamp=datetime.now(UTC),
            log_metadata=metadata
        )
        
        # Always log to file as backup
        self.file_logger.log(
            getattr(logging, level.upper()),
            f"{message} {json.dumps(metadata) if metadata else ''}"
        )
        
        self.buffer.append(log_entry)
        if len(self.buffer) >= self.buffer_size:
            asyncio.create_task(self.flush())
    
    async def flush(self):
        """Flush buffered logs to the API."""
        if not self.buffer:
            return
        
        logs_to_send = self.buffer[:]
        self.buffer.clear()
        
        batch = BridgeLogBatchCreate(logs=logs_to_send)
        batch_json = json.loads(batch.model_dump_json())
        
        for attempt in range(self.max_retries):
            try:
                if self.api_url.startswith("http://test"):
                    # Use test client for test URLs
                    response = self.test_client.post(
                        "/api/bridge/logs",
                        headers={
                            "X-API-Key": self.api_key,
                            "Content-Type": "application/json"
                        },
                        json=batch_json
                    )
                    if response.status_code >= 400:
                        raise httpx.HTTPStatusError(
                            f"HTTP Error {response.status_code}",
                            request=None,
                            response=response
                        )
                    # Ensure we got a successful response
                    if not response.json():
                        raise Exception("No response data received")
                else:
                    # Use httpx for real URLs
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"{self.api_url}/api/bridge/logs",
                            headers={
                                "X-API-Key": self.api_key,
                                "Content-Type": "application/json"
                            },
                            json=batch_json,
                            timeout=10.0
                        )
                        response.raise_for_status()
                return
            except Exception as e:
                logger.error(f"Failed to send logs (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt == self.max_retries - 1:
                    # On final attempt, log the error and keep the logs in memory
                    self.buffer.extend(logs_to_send)
                    if len(self.buffer) > self.buffer_size * 2:
                        # Prevent buffer from growing too large
                        self.buffer = self.buffer[-self.buffer_size:]
                await asyncio.sleep(min(2 ** attempt, 30))  # Exponential backoff
    
    async def _periodic_flush(self):
        """Periodically flush logs to the API."""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush: {str(e)}")
                await asyncio.sleep(1)  # Prevent tight loop on persistent errors
    
    def debug(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a debug message."""
        self.log("DEBUG", message, metadata)
    
    def info(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log an info message."""
        self.log("INFO", message, metadata)
    
    def warning(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a warning message."""
        self.log("WARNING", message, metadata)
    
    def error(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log an error message."""
        self.log("ERROR", message, metadata) 