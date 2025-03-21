import pytest
from datetime import datetime, timedelta, UTC
from fastapi import FastAPI
from fastapi.testclient import TestClient
import json
import asyncio
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from mcp_gateway.models.base import Base, get_db
from mcp_gateway.models.auth import AppID, APIKey, AppType, AppIDCreate, APIKeyCreate
from mcp_gateway.services.auth import AuthService
from mcp_gateway.api.bridge import router as bridge_router
from mcp_gateway.api.auth import router as auth_router
from mcp_gateway.schemas.auth import BridgeLogCreate, BridgeLogBatchCreate
from mcp_gateway.core.logging import BridgeLogger

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
async def test_log_creation_and_retrieval(client, test_app_and_key):
    """Test creating and retrieving logs through the API."""
    app, api_key = test_app_and_key
    
    # Create test logs
    test_logs = BridgeLogBatchCreate(logs=[
        BridgeLogCreate(
            level="INFO",
            message="Test log message 1",
            connection_id="test-connection-1",
            timestamp=datetime.now(UTC),
            log_metadata={"test_key": "test_value"}
        ),
        BridgeLogCreate(
            level="ERROR",
            message="Test log message 2",
            connection_id="test-connection-1",
            timestamp=datetime.now(UTC),
            log_metadata={"error_code": 123}
        )
    ])
    
    # Send logs to API
    response = client.post(
        "/api/bridge/logs",
        headers={"X-API-Key": api_key},
        json=json.loads(test_logs.model_dump_json())
    )
    assert response.status_code == 200
    created_logs = response.json()
    assert len(created_logs) == 2
    assert created_logs[0]["level"] == "INFO"
    assert created_logs[1]["level"] == "ERROR"
    
    # Retrieve logs
    response = client.get(
        f"/api/bridge/logs/{app.id}",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    log_list = response.json()
    assert log_list["total"] == 2
    assert len(log_list["logs"]) == 2
    
    # Test filtering by level
    response = client.get(
        f"/api/bridge/logs/{app.id}?level=ERROR",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    error_logs = response.json()
    assert error_logs["total"] == 1
    assert error_logs["logs"][0]["level"] == "ERROR"
    
    # Test filtering by connection_id
    response = client.get(
        f"/api/bridge/logs/{app.id}?connection_id=test-connection-1",
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == 200
    connection_logs = response.json()
    assert connection_logs["total"] == 2

@pytest.mark.asyncio
async def test_bridge_logger(test_app_and_key, test_app):
    """Test the BridgeLogger class functionality."""
    app, api_key = test_app_and_key
    
    # Create a test client with the app
    client = TestClient(test_app)
    
    # Create a BridgeLogger instance
    logger = BridgeLogger(
        app_id=app.id,
        connection_id="test-connection",
        api_key=api_key,
        api_url="http://test",  # Use a fixed test URL
        buffer_size=2,  # Small buffer size for testing
        flush_interval=1.0,  # Short flush interval for testing
        test_client=client  # Pass the test client
    )
    
    try:
        # Start the logger
        logger.start()
        
        # Log some messages
        logger.info("Test info message", {"test": "metadata"})
        logger.error("Test error message", {"error": "details"})
        
        # Wait for automatic flush
        await asyncio.sleep(2)
        
        # Ensure logs are flushed
        await logger.flush()
        
        # Verify logs were sent to API
        response = client.get(
            f"/api/bridge/logs/{app.id}",
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        log_list = response.json()
        assert log_list["total"] == 2
        assert len(log_list["logs"]) == 2
        
        # Verify log contents
        logs = sorted(log_list["logs"], key=lambda x: x["level"])
        assert logs[0]["level"] == "ERROR"
        assert logs[0]["message"] == "Test error message"
        assert logs[0]["log_metadata"] == {"error": "details"}
        assert logs[1]["level"] == "INFO"
        assert logs[1]["message"] == "Test info message"
        assert logs[1]["log_metadata"] == {"test": "metadata"}
    finally:
        # Stop the logger
        await logger.stop() 