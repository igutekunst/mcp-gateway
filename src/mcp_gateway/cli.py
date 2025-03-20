import typer
from rich.console import Console
from rich.table import Table
import uvicorn
import asyncio
import json
import subprocess
import os
import sys
import websockets
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode

from .main import app
from .models.base import AsyncSessionLocal
from .services.auth import AuthService
from .schemas.auth import AppIDCreate, APIKeyCreate
from .models.auth import AppType

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
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    # Print frontend output in a separate thread
    def print_output():
        for line in frontend_process.stdout:
            console.print(f"[blue]Frontend:[/blue] {line}", end="")
    
    import threading
    output_thread = threading.Thread(target=print_output, daemon=True)
    output_thread.start()
    
    try:
        # Run backend with reload enabled using import string
        uvicorn.run(
            "mcp_gateway.main:app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=[str(Path(__file__).parent)]
        )
    finally:
        # Cleanup frontend process
        frontend_process.terminate()
        try:
            frontend_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            frontend_process.kill()

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
    type: AppType = typer.Option(AppType.TOOL_PROVIDER, help="Type of app (tool_provider or agent)"),
    description: str = typer.Option(None, help="Description of the app"),
):
    """Create a new app ID."""
    async def _create_app():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            app = await auth_service.create_app_id(AppIDCreate(
                name=name,
                type=type,
                description=description
            ))
            return app

    app = asyncio.run(_create_app())
    console.print(f"Created [green]{app.type.value}[/green] app [blue]{app.name}[/blue] with ID: [yellow]{app.app_id}[/yellow]")

@cli.command()
def create_key(
    name: str = typer.Argument(..., help="Name of the API key"),
    app_id: int = typer.Argument(..., help="ID of the app to create the key for"),
):
    """Create a new API key for an app."""
    async def _create_key():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            key, secret = await auth_service.create_api_key(APIKeyCreate(
                name=name,
                app_id=app_id
            ))
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
    table.add_column("Type", style="magenta")
    table.add_column("Description")
    table.add_column("Status", style="yellow")

    for app in apps:
        table.add_row(
            str(app.id),
            app.app_id,
            app.name,
            app.type.value if app.type else "unknown",
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

@cli.command()
def bridge(
    api_key: str = typer.Option(..., help="API key for authentication", envvar="MCP_API_KEY"),
    host: str = typer.Option("localhost", help="MCP server host"),
    port: int = typer.Option(8000, help="MCP server port"),
):
    """
    Connect to MCP server as a bridge client.
    This allows the CLI to act as a bridge between local commands and the MCP server.
    """
    async def run_bridge():
        # Initial connection to get WebSocket URL
        url = f"ws://{host}:{port}/api/bridge/connect"
        headers = {"X-API-Key": api_key}
        
        try:
            async with websockets.connect(url, additional_headers=headers) as websocket:
                console.print("[green]Connected to MCP server[/green]")
                console.print("Listening for commands... Press Ctrl+C to exit")
                
                try:
                    while True:
                        message = await websocket.recv()
                        try:
                            command = json.loads(message)
                            console.print(f"[blue]Received command:[/blue] {command}")
                            # TODO: Execute command and send response
                            response = {"status": "success", "result": "Command received"}
                            await websocket.send(json.dumps(response))
                        except json.JSONDecodeError:
                            console.print(f"[yellow]Received invalid JSON message:[/yellow] {message}")
                except websockets.exceptions.ConnectionClosed:
                    console.print("[red]WebSocket connection closed[/red]")
                except KeyboardInterrupt:
                    console.print("\n[yellow]Bridge connection terminated by user[/yellow]")
        
        except websockets.exceptions.WebSocketException as e:
            console.print(f"[red]Failed to connect to MCP server:[/red] {str(e)}")

    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        console.print("\n[yellow]Bridge terminated[/yellow]")

if __name__ == "__main__":
    cli() 