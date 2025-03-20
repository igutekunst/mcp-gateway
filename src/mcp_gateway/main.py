from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .api.auth import router as auth_router
from .models.base import Base, engine

class HealthResponse(BaseModel):
    status: str
    version: str
    started_at: datetime
    uptime_seconds: float

class AppState:
    def __init__(self):
        self.started_at = datetime.utcnow()

app_state = AppState()

app = FastAPI(
    title="MCP Gateway",
    description="MCP Gateway Server - Tool and Agent Management Gateway",
    version="0.1.0",
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite's default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint that provides basic server status and uptime information.
    Useful for monitoring and debugging.
    """
    now = datetime.utcnow()
    uptime = (now - app_state.started_at).total_seconds()
    
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        started_at=app_state.started_at,
        uptime_seconds=uptime,
    )

@app.on_event("startup")
async def startup():
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 