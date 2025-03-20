from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.auth import router as auth_router
from .api.health import router as health_router
from .models.base import Base, engine

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

# Include API routers
app.include_router(auth_router, prefix="/api")
app.include_router(health_router, prefix="/api")

# Mount static files
static_dir = Path(__file__).parent / "static"
app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

# Serve index.html for all non-API routes to support client-side routing
@app.get("/{full_path:path}")
async def serve_spa(request: Request, full_path: str):
    if full_path.startswith("api/"):
        return {"detail": "Not Found"}
    return FileResponse(str(static_dir / "index.html"))

@app.on_event("startup")
async def startup():
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 