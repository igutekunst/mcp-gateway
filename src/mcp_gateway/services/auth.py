import secrets
import uuid
from datetime import datetime, UTC
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import bcrypt
from fastapi import Depends, HTTPException, Header
from typing import Optional, List

from ..models.auth import AppID, APIKey, AppType, BridgeLog
from ..schemas.auth import AppIDCreate, APIKeyCreate, BridgeLogCreate, BridgeLogBatchCreate
from ..models.base import get_db

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_app_id(self, app: AppIDCreate) -> AppID:
        """Create a new app ID with a unique identifier."""
        app_id_str = str(uuid.uuid4())
        db_app = AppID(
            app_id=app_id_str,
            name=app.name,
            description=app.description,
            type=app.type,
        )
        self.db.add(db_app)
        await self.db.commit()
        await self.db.refresh(db_app)
        return db_app

    async def create_api_key(self, api_key: APIKeyCreate) -> tuple[APIKey, str]:
        """Create a new API key and return both the model and the raw key."""
        key = secrets.token_urlsafe(32)
        key_bytes = key.encode('utf-8')
        salt = bcrypt.gensalt()
        key_hash = bcrypt.hashpw(key_bytes, salt).decode('utf-8')
        
        db_key = APIKey(
            key_hash=key_hash,
            name=api_key.name,
            app_id=api_key.app_id,
        )
        self.db.add(db_key)
        await self.db.commit()
        await self.db.refresh(db_key)
        return db_key, key

    async def update_last_connected(self, app_id: int) -> None:
        """Update the last_connected timestamp for an app."""
        app = await self.db.get(AppID, app_id)
        if app:
            app.last_connected = datetime.now(UTC)
            await self.db.commit()

    async def verify_api_key(self, api_key: str) -> AppID | None:
        """Verify an API key and return the associated app if valid."""
        # Find all active API keys
        stmt = select(APIKey).options(selectinload(APIKey.app)).where(APIKey.is_active == True)
        result = await self.db.execute(stmt)
        keys = result.scalars().all()
        
        # Check each key's hash
        key_bytes = api_key.encode('utf-8')
        for key in keys:
            if bcrypt.checkpw(key_bytes, key.key_hash.encode('utf-8')):
                # Update last used timestamp
                key.last_used_at = datetime.now(UTC)
                await self.db.commit()
                return key.app
        
        return None

    async def get_app_by_id(self, app_id: str) -> AppID | None:
        """Get an app by its ID."""
        stmt = select(AppID).where(AppID.app_id == app_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_apps(self, type: AppType | None = None) -> list[AppID]:
        """List all registered apps, optionally filtered by type."""
        stmt = select(AppID)
        if type is not None:
            stmt = stmt.where(AppID.type == type)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_api_keys(self, app_id: int | None = None) -> list[APIKey]:
        """List all API keys, optionally filtered by app ID."""
        stmt = select(APIKey)
        if app_id is not None:
            stmt = stmt.where(APIKey.app_id == app_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def _get_api_key_by_key(self, api_key: str) -> Optional[APIKey]:
        """Get API key by raw key value."""
        # Find all active API keys
        stmt = select(APIKey).where(APIKey.is_active == True)
        result = await self.db.execute(stmt)
        keys = result.scalars().all()
        
        # Check each key's hash
        key_bytes = api_key.encode('utf-8')
        for key in keys:
            if bcrypt.checkpw(key_bytes, key.key_hash.encode('utf-8')):
                return key
        
        return None

    async def get_app_by_api_key(self, api_key: str) -> Optional[AppID]:
        """Get application by API key."""
        key = await self._get_api_key_by_key(api_key)
        if key and key.is_active:
            key.last_used_at = datetime.now(UTC)
            await self.db.commit()
            # Get app directly from the database using the numeric ID
            stmt = select(AppID).where(AppID.id == key.app_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        return None

    @staticmethod
    async def get_api_key(
        api_key: Optional[str] = Header(None, alias="X-API-Key"),
        db: AsyncSession = Depends(get_db)
    ) -> Optional[str]:
        """FastAPI dependency to get and validate API key"""
        if not api_key:
            return None
            
        auth_service = AuthService(db)
        app = await auth_service.verify_api_key(api_key)
        if not app:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return api_key

    async def create_logs(self, app_id: int, logs: BridgeLogBatchCreate) -> List[BridgeLog]:
        """Create multiple log entries for an app."""
        db_logs = []
        for log in logs.logs:
            db_log = BridgeLog(
                app_id=app_id,
                timestamp=log.timestamp or datetime.now(UTC),
                level=log.level,
                message=log.message,
                connection_id=log.connection_id,
                log_metadata=log.log_metadata
            )
            self.db.add(db_log)
            db_logs.append(db_log)
        
        await self.db.commit()
        for log in db_logs:
            await self.db.refresh(log)
        return db_logs

    async def get_logs(
        self,
        app_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        connection_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[BridgeLog], int]:
        """Get logs for an app with filtering."""
        # Build query conditions
        conditions = [BridgeLog.app_id == app_id]
        if start_time:
            conditions.append(BridgeLog.timestamp >= start_time)
        if end_time:
            conditions.append(BridgeLog.timestamp <= end_time)
        if level:
            conditions.append(BridgeLog.level == level)
        if connection_id:
            conditions.append(BridgeLog.connection_id == connection_id)

        # Get total count
        count_query = select(BridgeLog).where(and_(*conditions))
        total = len((await self.db.execute(count_query)).all())

        # Get paginated results
        query = select(BridgeLog).where(and_(*conditions)) \
            .order_by(BridgeLog.timestamp.desc()) \
            .offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        logs = result.scalars().all()
        
        return logs, total 