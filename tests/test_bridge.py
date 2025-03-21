import pytest
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import asyncio
import pytest_asyncio
import json

from mcp_gateway.models.base import Base, get_db
from mcp_gateway.models.auth import AppID, APIKey, AppType, AppIDCreate, APIKeyCreate
from mcp_gateway.services.auth import AuthService
from mcp_gateway.api.bridge import router as bridge_router
from mcp_gateway.api.auth import router as auth_router
from mcp_gateway.main import app

# Create test database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DATABASE_URL, echo=True)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(bridge_router, prefix="/api/bridge")
    
    # Add dependency overrides
    async def get_test_db():
        async with TestingSessionLocal() as session:
            yield session
    
    app.dependency_overrides[get_db] = get_test_db
    return app

@pytest.fixture
def client(test_app):
    return TestClient(test_app)

@pytest_asyncio.fixture
async def test_app_and_key(db):
    auth_service = AuthService(db)
    app = await auth_service.create_app_id(AppIDCreate(
        name="Test App",
        type=AppType.TOOL_PROVIDER,
        description="Test app for bridge"
    ))
    key, secret = await auth_service.create_api_key(APIKeyCreate(
        name="Test Key",
        app_id=app.id
    ))
    return app, secret

@pytest.mark.asyncio
async def test_bridge_heartbeat(client, test_app_and_key, db):
    app, api_key = test_app_and_key
    
    # Send heartbeat
    response = client.post(
        "/api/bridge/heartbeat",
        headers={"X-API-Key": api_key},
        json={"status": "alive"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    
    # Verify last_connected was updated
    async with TestingSessionLocal() as session:
        auth_service = AuthService(session)
        updated_app = await auth_service.get_app_by_id(app.app_id)
        assert updated_app.last_connected is not None
        assert datetime.utcnow() - updated_app.last_connected < timedelta(seconds=5)

@pytest.mark.asyncio
async def test_bridge_heartbeat_invalid_key(client, db):
    response = client.post(
        "/api/bridge/heartbeat",
        headers={"X-API-Key": "invalid-key"},
        json={"status": "alive"}
    )
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]

@pytest.mark.asyncio
async def test_bridge_heartbeat_missing_key(client):
    response = client.post(
        "/api/bridge/heartbeat",
        json={"status": "alive"}
    )
    assert response.status_code == 422
    assert "X-API-Key" in response.json()["detail"][0]["loc"]

@pytest.mark.asyncio
async def test_mcp_protocol(test_app, test_app_and_key):
    """Test the full MCP protocol flow"""
    app, api_key = test_app_and_key
    
    with TestClient(test_app).websocket_connect(
        "/api/bridge/connect",
        headers={"X-API-Key": api_key}
    ) as websocket:
        # Check connection established message
        response = websocket.receive_json()
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "connection"
        assert response["result"]["type"] == "connection_established"
        assert "connection_id" in response["result"]
        
        # Send initialize request
        websocket.send_json({
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": "1"
        })
        
        # Check capabilities response
        response = websocket.receive_json()
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "1"
        assert "result" in response
        capabilities = response["result"]
        
        # Verify protocol version and capabilities
        assert capabilities["protocol"]["version"] == "2024-11-05"
        assert capabilities["protocol"]["capabilities"]["tools"] is True
        assert "tools" in capabilities
        
        # Test error handling - invalid method
        websocket.send_json({
            "jsonrpc": "2.0",
            "method": "invalid_method",
            "id": "2"
        })
        
        response = websocket.receive_json()
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "2"
        assert "error" in response
        assert response["error"]["code"] == -32601
        assert response["error"]["message"] == "Method 'invalid_method' not found"
        
        # Test error handling - invalid params
        websocket.send_json({
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"invalid": "params"},
            "id": "3"
        })
        
        response = websocket.receive_json()
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "3"
        assert "error" in response
        assert response["error"]["code"] == -32602
        assert "Invalid params" in response["error"]["message"]
        
        # Test error handling - invalid request
        websocket.send_json({
            "invalid": "request"
        })
        
        response = websocket.receive_json()
        assert response["jsonrpc"] == "2.0"
        assert "error" in response
        assert response["error"]["code"] == -32600
        assert "Invalid Request" in response["error"]["message"] 