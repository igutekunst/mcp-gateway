import typer
from rich.console import Console
from rich.table import Table
import time
import uvicorn
import asyncio
import json
import subprocess
import websockets.client
import threading
import logging
import httpx
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
import os
import sys
import select
import traceback
import fcntl
import errno
import io

from .main import app
from .models.base import AsyncSessionLocal
from .services.auth import AuthService
from .schemas.auth import AppIDCreate, APIKeyCreate
from .models.auth import AppType
from .settings import initialize_admin_password, settings

cli = typer.Typer()
console = Console()

def setup_logging():
    """Configure logging for the application."""
    log_dir = Path(os.path.expanduser("~/Library/Logs/mcp-gateway"))
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "mcp-gateway.log"
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stderr)
        ]
    )

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
    """Create a new app ID (defaults to tool_provider type)."""
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
def create_tool_provider(
    name: str = typer.Argument(..., help="Name of the tool provider"),
    description: str = typer.Option(None, help="Description of the tool provider"),
):
    """Create a new tool provider app ID."""
    async def _create_tool_provider():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            app = await auth_service.create_app_id(AppIDCreate(
                name=name,
                type=AppType.TOOL_PROVIDER,
                description=description
            ))
            return app

    app = asyncio.run(_create_tool_provider())
    console.print(f"Created [green]tool_provider[/green] [blue]{app.name}[/blue] with ID: [yellow]{app.app_id}[/yellow]")

@cli.command()
def create_agent(
    name: str = typer.Argument(..., help="Name of the agent"),
    description: str = typer.Option(None, help="Description of the agent"),
):
    """Create a new agent app ID."""
    async def _create_agent():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            app = await auth_service.create_app_id(AppIDCreate(
                name=name,
                type=AppType.AGENT,
                description=description
            ))
            return app

    app = asyncio.run(_create_agent())
    console.print(f"Created [green]agent[/green] [blue]{app.name}[/blue] with ID: [yellow]{app.app_id}[/yellow]")

@cli.command()
def create_key(
    name: str = typer.Argument(..., help="Name of the API key"),
    app_id: str = typer.Argument(..., help="App ID (UUID) to create the key for"),
):
    """Create a new API key for an app."""
    async def _create_key():
        async with AsyncSessionLocal() as session:
            auth_service = AuthService(session)
            # First get the app by its UUID
            app = await auth_service.get_app_by_id(app_id)
            if not app:
                raise ValueError(f"App with ID {app_id} not found")
            
            # Create key using the numeric ID
            key, secret = await auth_service.create_api_key(APIKeyCreate(
                name=name,
                app_id=app.id
            ))
            return key, secret, app

    try:
        key, secret, app = asyncio.run(_create_key())
        console.print(f"Created API key [green]{key.name}[/green] for app [blue]{app.name}[/blue]")
        console.print(f"Secret (save this, it won't be shown again): [red]{secret}[/red]")
    except ValueError as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(code=1)

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
    """Run the MCP bridge over stdin/stdout."""
    from .mcp_server import MCPServer
    from .json_rpc import JSONRPCServer

    # Set up logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting MCP bridge")

    try:
        # Create and configure MCP server
        mcp = MCPServer()
        
        # Create JSON-RPC server
        rpc = JSONRPCServer()
        
        # Register MCP methods
        rpc.register_method("initialize", mcp.handle_initialize)
        rpc.register_method("initialized", mcp.handle_initialized)
        rpc.register_method("tools/list", mcp.handle_tools_list)
        rpc.register_method("tools/call", mcp.handle_tools_call)

        # Run the event loop
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(rpc.serve_forever())
        finally:
            loop.close()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        sys.exit(0)
    except Exception:
        logger.exception("Unexpected error in bridge command")
        sys.exit(1)

@cli.command()
def set_admin_password(
    password: str = typer.Option(
        ...,
        prompt=True,
        confirmation_prompt=True,
        hide_input=True,
        help="Set the admin password for the web interface"
    )
):
    """Set the admin password for the web interface."""
    try:
        initialize_admin_password(password)
        # Save to environment file
        env_file = Path(".env")
        env_contents = []
        
        # Read existing contents
        if env_file.exists():
            with open(env_file) as f:
                env_contents = [
                    line for line in f.readlines()
                    if not line.startswith("MCP_ADMIN_PASSWORD_HASH=")
                ]
        
        # Add new password hash
        env_contents.append(f"MCP_ADMIN_PASSWORD_HASH={settings.ADMIN_PASSWORD_HASH}\n")
        
        # Write back
        with open(env_file, "w") as f:
            f.writelines(env_contents)
            
        typer.echo("Admin password set successfully!")
    except Exception as e:
        typer.echo(f"Error setting admin password: {str(e)}", err=True)
        raise typer.Exit(1)

if __name__ == "__main__":
    cli() 