"""
MCP Bridge Live Test Client

This script serves as a live test client for the MCP (Message Communication Protocol) bridge,
simulating how Claude Desktop would interact with the bridge. It's designed for:

1. Live Testing & Verification:
   - Real-time testing of the WebSocket connection and protocol
   - Verification of the bridge's behavior in a production-like environment
   - Quick sanity checks during development

2. Integration Testing:
   - Tests the full stack from WebSocket connection to tool execution
   - Verifies authentication flow with API keys
   - Ensures JSON-RPC protocol compliance
   - Validates tool registration and execution

3. Development Support:
   - Provides immediate feedback on protocol changes
   - Helps debug connection and communication issues
   - Simulates real client behavior for testing

Unlike unit tests, this tool:
- Connects to a live server instance
- Uses real WebSocket connections
- Executes actual tool commands
- Provides interactive feedback
- Can be used for manual testing and debugging

Usage:
1. Ensure the MCP server is running on localhost:8000
2. Run this script to test the connection and protocol
3. Check the output for proper protocol compliance and error handling
"""

import asyncio
import websockets
import json

async def test_client():
    uri = 'ws://localhost:8000/api/bridge/connect'
    headers = {
        'X-API-Key': '8uHmczDVn092HzWewFaTPpomZdkbfOFf5ExGfzmtdzw'
    }
    
    async with websockets.connect(
        uri,
        additional_headers=headers
    ) as websocket:
        # Wait for connection established message
        response = await websocket.recv()
        print("Connection:", response)
        
        # Send initialize request
        await websocket.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": "1"
        }))
        
        response = await websocket.recv()
        print("\nInitialize Response:", response)
        response_data = json.loads(response)
        if "result" in response_data:
            print("\nCapabilities:")
            print("- Protocol Version:", response_data["result"]["protocol"]["version"])
            print("- Available Tools:", list(response_data["result"]["tools"].keys()))
        
        # Test tool method call
        await websocket.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "system_info.get_cpu_usage",
            "id": "2"
        }))
        
        response = await websocket.recv()
        print("\nCPU Usage Response:", response)
        
        # Test error handling - invalid method
        await websocket.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "invalid_method",
            "id": "3"
        }))
        
        response = await websocket.recv()
        print("\nError Response:", response)

if __name__ == "__main__":
    asyncio.run(test_client())
