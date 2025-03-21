import typer
from rich.console import Console
from rich.table import Table
import time
import uvicorn
import asyncio
import json
import subprocess
import websockets
import threading
import logging
import httpx
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
import os

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
    
    # Set up environment variables for the frontend process
    env = {
        **os.environ,
        'VITE_API_URL': f'http://{host}:{port}',
        'VITE_DEV_SERVER_PORT': '5173',
    }
    
    # Start frontend dev server with proper environment
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        env=env,
        shell=True if os.name == 'nt' else False,  # Use shell on Windows
    )
    
    # Print frontend output in a separate thread
    def print_frontend_output():
        try:
            while True:
                line = frontend_process.stdout.readline()
                if not line and frontend_process.poll() is not None:
                    break
                if line:
                    console.print(f"[blue]Frontend:[/blue] {line}", end="")
        except Exception as e:
            console.print(f"[red]Frontend output error:[/red] {str(e)}")
    
    # Create and start frontend output thread
    frontend_thread = threading.Thread(target=print_frontend_output, daemon=True)
    frontend_thread.start()

    # Create a custom uvicorn logger that prefixes output
    class PrefixedHandler(logging.StreamHandler):
        def emit(self, record):
            msg = self.format(record)
            console.print(f"[green]Backend:[/green] {msg}")

    # Configure uvicorn logging
    logging.getLogger("uvicorn").handlers = [PrefixedHandler()]
    
    try:
        # Run backend with reload enabled using import string
        uvicorn.run(
            "mcp_gateway.main:app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=[str(Path(__file__).parent)],
            log_config=None  # Disable default uvicorn logging config
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down servers...[/yellow]")
    finally:
        # Cleanup frontend process
        if frontend_process.poll() is None:  # Only if process is still running
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()
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
    console.print(f"Created [green]{app.type}[/green] app [blue]{app.name}[/blue] with ID: [yellow]{app.app_id}[/yellow]")

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
            app.type,
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
    async def send_heartbeat(api_key: str, host: str, port: int):
        """Send periodic heartbeats to the server."""
        url = f"http://{host}:{port}/api/bridge/heartbeat"
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    resp = await client.post(url, headers=headers, json={"status": "alive"})
                    if resp.status_code == 401:
                        return
                    elif resp.status_code == 405:
                        return
                    elif resp.status_code != 200:
                        pass
                except httpx.ConnectError:
                    pass
                except Exception:
                    pass
                await asyncio.sleep(5)  # Send heartbeat every 5 seconds

    async def run_bridge():
        # Start heartbeat task first
        heartbeat_task = asyncio.create_task(send_heartbeat(api_key, host, port))
        
        # Initial connection to get WebSocket URL
        url = f"ws://{host}:{port}/api/bridge/connect"
        headers = {"X-API-Key": api_key}
        
        try:
            while True:  # Reconnection loop
                try:
                    async with websockets.connect(url, additional_headers=headers) as websocket:
                        try:
                            while True:
                                message = await websocket.recv()
                                try:
                                    command = json.loads(message)
                                    # Process command...
                                except json.JSONDecodeError:
                                    pass
                        except websockets.exceptions.ConnectionClosed as e:
                            if e.code == 4001:
                                heartbeat_task.cancel()  # Stop heartbeat on auth failure
                                return
                            else:
                                await asyncio.sleep(5)  # Wait before reconnecting
                except websockets.exceptions.InvalidStatusCode as e:
                    if e.status_code == 403:
                        heartbeat_task.cancel()  # Stop heartbeat on auth failure
                        return
                    else:
                        return
                except websockets.exceptions.ConnectionClosed:
                    await asyncio.sleep(5)  # Wait before reconnecting
                except Exception:
                    await asyncio.sleep(5)  # Wait before reconnecting
        except KeyboardInterrupt:
            heartbeat_task.cancel()
        except Exception:
            heartbeat_task.cancel()

    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    cli() 