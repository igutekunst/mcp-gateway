import asyncio
import json
import logging
import sys
from typing import Any, Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)

class JSONRPCError(Exception):
    """Base class for JSON-RPC protocol errors."""
    def __init__(self, code: int, message: str, data: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)

class MethodNotFoundError(JSONRPCError):
    def __init__(self, method: str):
        super().__init__(-32601, f"Method not found: {method}")

class ParseError(JSONRPCError):
    def __init__(self, message: str):
        super().__init__(-32700, f"Parse error: {message}")

class InvalidRequestError(JSONRPCError):
    def __init__(self, message: str):
        super().__init__(-32600, f"Invalid Request: {message}")

class JSONRPCServer:
    """JSON-RPC 2.0 server implementation over stdin/stdout."""

    def __init__(self):
        self.methods: Dict[str, Callable] = {}
        self._request_counter = 0

    def _format_error(self, error: Union[JSONRPCError, Exception]) -> Dict[str, Any]:
        """Format an error into a JSON-RPC error object."""
        if isinstance(error, JSONRPCError):
            error_dict = {
                "code": error.code,
                "message": error.message
            }
            if error.data:
                error_dict["data"] = error.data
            return error_dict
        
        # Convert MCPError to appropriate JSON-RPC error
        if hasattr(error, 'code') and hasattr(error, 'message'):
            return {
                "code": error.code,
                "message": error.message,
                "data": getattr(error, 'data', None)
            }
        
        # Unexpected errors become internal error
        return {
            "code": -32603,
            "message": f"Internal error: {str(error)}"
        }

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle a single JSON-RPC request."""
        try:
            # Validate JSON-RPC version
            if request.get("jsonrpc") != "2.0":
                raise InvalidRequestError("only JSON-RPC 2.0 is supported")

            method = request.get("method")
            if not method:
                raise InvalidRequestError("method is required")

            params = request.get("params", {})
            req_id = request.get("id")

            # Log the incoming request details
            logger.debug(f"Handling JSON-RPC request:")
            logger.debug(f"  Method: {method}")
            logger.debug(f"  Params: {params}")
            logger.debug(f"  ID: {req_id}")

            # Look up method handler
            handler = self.methods.get(method)
            if not handler:
                raise MethodNotFoundError(method)

            # Call handler and get result
            result = await handler(params)
            
            # Only return response for requests (not notifications)
            if req_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": result
                }
            return None

        except Exception as e:
            logger.exception("Error handling request")
            if req_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": self._format_error(e)
                }
            return None

    def register_method(self, name: str, handler: Callable) -> None:
        """Register a method handler."""
        self.methods[name] = handler

    async def _read_request(self) -> Optional[Dict[str, Any]]:
        """Read a single request from stdin."""
        try:
            line = sys.stdin.readline()
            if not line:
                return None
            return json.loads(line)
        except json.JSONDecodeError as e:
            raise ParseError(str(e))

    def _write_response(self, response: Dict[str, Any]) -> None:
        """Write a response to stdout."""
        try:
            json.dump(response, sys.stdout)
            sys.stdout.write('\n')
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Error writing response: {e}")
            # Not much we can do if we can't write to stdout
            raise

    async def serve_forever(self) -> None:
        """Main server loop."""
        logger.info("Starting JSON-RPC server")
        while True:
            try:
                request = await self._read_request()
                if request is None:
                    logger.info("Received EOF, shutting down")
                    break

                logger.debug(f"Received request: {request}")
                response = await self.handle_request(request)
                
                if response is not None:
                    logger.debug(f"Sending response: {response}")
                    self._write_response(response)

            except Exception as e:
                logger.exception("Unexpected error in server loop")
                # Try to send error response if possible
                try:
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": self._format_error(e)
                    }
                    self._write_response(error_response)
                except:
                    # If we can't even send the error, just log it
                    logger.critical("Could not send error response", exc_info=True) 