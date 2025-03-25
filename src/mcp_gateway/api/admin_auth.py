from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime, timedelta
import secrets
import json
from typing import Dict, Optional
from ..settings import verify_admin_password, settings
from pydantic import BaseModel

router = APIRouter(tags=["admin"])

# Simple in-memory session store (this should be replaced with a database solution in production)
sessions: Dict[str, datetime] = {}

# Session cleanup interval (remove expired sessions)
def cleanup_expired_sessions():
    now = datetime.utcnow()
    expired = [sid for sid, expiry in sessions.items() if expiry < now]
    for sid in expired:
        sessions.pop(sid, None)

class LoginRequest(BaseModel):
    password: str

class SessionResponse(BaseModel):
    authenticated: bool
    expires_at: Optional[str] = None

def create_session() -> tuple[str, datetime]:
    """Create a new session with an expiration time."""
    session_id = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES)
    sessions[session_id] = expires_at
    return session_id, expires_at

def get_session(request: Request) -> tuple[bool, Optional[datetime]]:
    """Validate session from cookie."""
    session_id = request.cookies.get("mcp_session")
    if not session_id or session_id not in sessions:
        return False, None
    
    expires_at = sessions.get(session_id)
    if not expires_at or expires_at < datetime.utcnow():
        # Session expired
        if session_id in sessions:
            sessions.pop(session_id)
        return False, None
    
    return True, expires_at

@router.post("/login")
async def login(login_data: LoginRequest, response: Response):
    """Login admin user and set session cookie."""
    cleanup_expired_sessions()
    
    if not verify_admin_password(login_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create new session
    session_id, expires_at = create_session()
    
    # Set cookie
    response.set_cookie(
        key="mcp_session",
        value=session_id,
        httponly=True,
        secure=not settings.ALLOW_INSECURE,
        samesite="lax",
        max_age=settings.SESSION_EXPIRE_MINUTES * 60,
        expires=expires_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
    )
    
    return {"expires_at": expires_at.isoformat()}

@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout admin user and clear session cookie."""
    session_id = request.cookies.get("mcp_session")
    if session_id and session_id in sessions:
        sessions.pop(session_id)
    
    response.delete_cookie(key="mcp_session")
    return {"status": "success"}

@router.get("/session")
async def check_session(request: Request):
    """Check if the current session is valid."""
    authenticated, expires_at = get_session(request)
    
    if authenticated:
        return SessionResponse(
            authenticated=True,
            expires_at=expires_at.isoformat() if expires_at else None
        )
    
    return SessionResponse(authenticated=False) 