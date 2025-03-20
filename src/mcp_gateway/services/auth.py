import secrets
import uuid
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.hash import bcrypt

from ..models.auth import AppID, APIKey
from ..schemas.auth import AppIDCreate, APIKeyCreate

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_app_id(self, app: AppIDCreate) -> tuple[AppID, str]:
        """Create a new app ID with a unique identifier."""
        app_id_str = str(uuid.uuid4())
        db_app = AppID(
            app_id=app_id_str,
            name=app.name,
            description=app.description,
        )
        self.db.add(db_app)
        await self.db.commit()
        await self.db.refresh(db_app)
        return db_app

    async def create_api_key(self, api_key: APIKeyCreate) -> tuple[APIKey, str]:
        """Create a new API key and return both the model and the raw key."""
        key = secrets.token_urlsafe(32)
        key_hash = bcrypt.hash(key)
        
        db_key = APIKey(
            key_hash=key_hash,
            name=api_key.name,
            app_id=api_key.app_id,
        )
        self.db.add(db_key)
        await self.db.commit()
        await self.db.refresh(db_key)
        return db_key, key

    async def verify_api_key(self, key: str) -> APIKey | None:
        """Verify an API key and return the associated model if valid."""
        stmt = select(APIKey).where(APIKey.is_active == True)
        result = await self.db.execute(stmt)
        api_keys = result.scalars().all()

        for api_key in api_keys:
            if bcrypt.verify(key, api_key.key_hash):
                api_key.last_used_at = datetime.utcnow()
                await self.db.commit()
                return api_key
        return None

    async def get_app_by_id(self, app_id: str) -> AppID | None:
        """Get an app by its ID."""
        stmt = select(AppID).where(AppID.app_id == app_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_apps(self) -> list[AppID]:
        """List all registered apps."""
        stmt = select(AppID)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_api_keys(self, app_id: int | None = None) -> list[APIKey]:
        """List all API keys, optionally filtered by app ID."""
        stmt = select(APIKey)
        if app_id is not None:
            stmt = stmt.where(APIKey.app_id == app_id)
        result = await self.db.execute(stmt)
        return result.scalars().all() 