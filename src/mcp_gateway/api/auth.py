from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from ..models.auth import AppType
from ..schemas.auth import (
    AppIDCreate,
    AppIDResponse,
    APIKeyCreate,
    APIKeyResponse,
    APIKeyWithSecret,
)
from ..services.auth import AuthService
from ..models.base import get_db

router = APIRouter(tags=["auth"])

@router.post("/apps", response_model=AppIDResponse)
async def create_app(
    app: AppIDCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new app ID."""
    auth_service = AuthService(db)
    db_app = await auth_service.create_app_id(app)
    return db_app

@router.get("/apps", response_model=List[AppIDResponse])
async def list_apps(
    type: Optional[AppType] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all registered apps, optionally filtered by type."""
    auth_service = AuthService(db)
    return await auth_service.list_apps(type)

@router.get("/apps/{app_id}", response_model=AppIDResponse)
async def get_app(
    app_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get an app by its ID."""
    auth_service = AuthService(db)
    db_app = await auth_service.get_app_by_id(app_id)
    if db_app is None:
        raise HTTPException(status_code=404, detail="App not found")
    return db_app

@router.post("/keys", response_model=APIKeyWithSecret)
async def create_api_key(
    api_key: APIKeyCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key."""
    auth_service = AuthService(db)
    db_key, key = await auth_service.create_api_key(api_key)
    return {**APIKeyResponse.model_validate(db_key).model_dump(), "key": key}

@router.get("/keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    app_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all API keys, optionally filtered by app ID."""
    auth_service = AuthService(db)
    return await auth_service.list_api_keys(app_id) 