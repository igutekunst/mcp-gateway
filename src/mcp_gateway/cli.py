import typer
from rich.console import Console
from rich.table import Table
import uvicorn
import asyncio
import json
import subprocess
import os
from pathlib import Path
from typing import Optional

from .main import app
from .models.base import AsyncSessionLocal
from .services.auth import AuthService

cli = typer.Typer()
console = Console()

@cli.command()
def dev(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
):
    """Run the MCP Admin server in development mode with hot-reloading frontend."""
    # Start frontend dev server
    frontend_dir = Path(__file__).parent.parent.parent / "frontend"
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    console.print("[green]Started frontend dev server[/green]")
    
    try:
        # Run backend with reload enabled
        uvicorn.run(app, host=host, port=port, reload=True)
    finally:
        # Cleanup frontend process
        frontend_process.terminate()
        frontend_process.wait()

@cli.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
):
    """Run the MCP Admin server."""
    uvicorn.run(app, host=host, port=port)

@cli.command()
def create_app(
    name: str = typer.Argument(..., help="Name of the app"),
    description: str = typer.Option(None, help="Description of the app"),
):
    """Create a new app ID."""
    async def _create_app():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            app = await auth_service.create_app_id({
                "name": name,
                "description": description
            })
            return app

    app = asyncio.run(_create_app())
    console.print(f"Created app [green]{app.name}[/green] with ID: [blue]{app.app_id}[/blue]")

@cli.command()
def create_key(
    name: str = typer.Argument(..., help="Name of the API key"),
    app_id: int = typer.Argument(..., help="ID of the app to create the key for"),
):
    """Create a new API key for an app."""
    async def _create_key():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            key, secret = await auth_service.create_api_key({
                "name": name,
                "app_id": app_id
            })
            return key, secret

    key, secret = asyncio.run(_create_key())
    console.print(f"Created API key [green]{key.name}[/green]")
    console.print(f"Secret (save this, it won't be shown again): [red]{secret}[/red]")

@cli.command()
def list_apps():
    """List all registered apps."""
    async def _list_apps():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            return await auth_service.list_apps()

    apps = asyncio.run(_list_apps())
    
    table = Table(title="Registered Apps")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("App ID", style="green")
    table.add_column("Name", style="blue")
    table.add_column("Description")
    table.add_column("Status", style="magenta")

    for app in apps:
        table.add_row(
            str(app.id),
            app.app_id,
            app.name,
            app.description or "",
            "Active" if app.is_active else "Inactive"
        )

    console.print(table)

@cli.command()
def list_keys(app_id: Optional[int] = typer.Option(None, help="Filter by app ID")):
    """List all API keys."""
    async def _list_keys():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            return await auth_service.list_api_keys(app_id)

    keys = asyncio.run(_list_keys())
    
    table = Table(title="API Keys")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("App ID", style="blue")
    table.add_column("Last Used", style="magenta")
    table.add_column("Status")

    for key in keys:
        table.add_row(
            str(key.id),
            key.name,
            str(key.app_id),
            str(key.last_used_at) if key.last_used_at else "Never",
            "Active" if key.is_active else "Inactive"
        )

    console.print(table)

import typer
from rich.console import Console
from rich.table import Table
import uvicorn
import asyncio
import json
from typing import Optional

from .main import app
from .models.base import AsyncSessionLocal
from .services.auth import AuthService

cli = typer.Typer()
console = Console()

@cli.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
):
    """Run the MCP Admin server."""
    uvicorn.run(app, host=host, port=port)

@cli.command()
def create_app(
    name: str = typer.Argument(..., help="Name of the app"),
    description: str = typer.Option(None, help="Description of the app"),
):
    """Create a new app ID."""
    async def _create_app():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            app = await auth_service.create_app_id({
                "name": name,
                "description": description
            })
            return app

    app = asyncio.run(_create_app())
    console.print(f"Created app [green]{app.name}[/green] with ID: [blue]{app.app_id}[/blue]")

@cli.command()
def create_key(
    name: str = typer.Argument(..., help="Name of the API key"),
    app_id: int = typer.Argument(..., help="ID of the app to create the key for"),
):
    """Create a new API key for an app."""
    async def _create_key():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            key, secret = await auth_service.create_api_key({
                "name": name,
                "app_id": app_id
            })
            return key, secret

    key, secret = asyncio.run(_create_key())
    console.print(f"Created API key [green]{key.name}[/green]")
    console.print(f"Secret (save this, it won't be shown again): [red]{secret}[/red]")

@cli.command()
def list_apps():
    """List all registered apps."""
    async def _list_apps():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            return await auth_service.list_apps()

    apps = asyncio.run(_list_apps())
    
    table = Table(title="Registered Apps")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("App ID", style="green")
    table.add_column("Name", style="blue")
    table.add_column("Description")
    table.add_column("Status", style="magenta")

    for app in apps:
        table.add_row(
            str(app.id),
            app.app_id,
            app.name,
            app.description or "",
            "Active" if app.is_active else "Inactive"
        )

    console.print(table)

@cli.command()
def list_keys(app_id: Optional[int] = typer.Option(None, help="Filter by app ID")):
    """List all API keys."""
    async def _list_keys():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            return await auth_service.list_api_keys(app_id)

    keys = asyncio.run(_list_keys())
    
    table = Table(title="API Keys")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("App ID", style="blue")
    table.add_column("Last Used", style="magenta")
    table.add_column("Status")

    for key in keys:
        table.add_row(
            str(key.id),
            key.name,
            str(key.app_id),
            str(key.last_used_at) if key.last_used_at else "Never",
            "Active" if key.is_active else "Inactive"
        )

    console.print(table)

if __name__ == "__main__":
    cli() 