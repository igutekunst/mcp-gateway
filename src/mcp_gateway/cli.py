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
    use_websocket_client: bool = typer.Option(False, help="Use as WebSocket client instead of stdin/stdout bridge"),
):
    """
    Connect to MCP server as a bridge client.
    By default, acts as a bridge between stdin/stdout and the MCP server (ideal for Claude).
    Use --use-websocket-client flag to behave as a WebSocket client instead.
    """
    if use_websocket_client:
        # WebSocket client mode (original mode)
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
                        async with websockets.client.connect(url, extra_headers=headers) as websocket:
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
    
    else:
        # Immediate stdout test before any configuration
        print("BRIDGE_TEST_START", flush=True)
        print(json.dumps({
            "jsonrpc": "2.0",
            "method": "test",
            "result": {"status": "Testing stdout before any configuration"},
            "id": "pre-config-test"
        }), flush=True)
        print("BRIDGE_TEST_END", flush=True)
        
        # Print directly to file descriptor 1 (stdout)
        try:
            os.write(1, b"DIRECT_FD_TEST\n")
        except Exception as e:
            print(f"Direct FD write failed: {e}", file=sys.stderr, flush=True)

        # Stdin/stdout bridge mode (default mode)
        import sys
        import time
        import select
        import threading
        import traceback
        
        # Ensure logs directory exists
        log_dir = Path(os.path.expanduser("~/Library/Logs/mcp-gateway"))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to acquire process lock
        lock_file_path = log_dir / "bridge.lock"
        lock_file = None

        # Helper function for consistent logging to stderr (available immediately)
        def log(message: str):
            """Log a message to stderr with consistent formatting."""
            print(f"[mcp-gateway bridge] {message}", file=sys.stderr, flush=True)

        def check_existing_process():
            """Check if another bridge process is running and send error response if it is."""
            if lock_file_path.exists():
                try:
                    with open(lock_file_path, 'r') as f:
                        old_pid = f.read().strip()
                        if old_pid:
                            try:
                                # Check if process is still running
                                os.kill(int(old_pid), 0)
                                log(f"Another bridge process (PID {old_pid}) is already running")
                                error_resp = {
                                    "jsonrpc": "2.0",
                                    "error": {
                                        "code": -32000,
                                        "message": "Another bridge process is already running"
                                    },
                                    "id": "0"
                                }
                                # Write error and exit immediately
                                sys.stdout.write(json.dumps(error_resp) + "\n")
                                sys.stdout.flush()
                                sys.exit(1)
                            except (ValueError, ProcessLookupError):
                                # Process not running, remove stale lock
                                try:
                                    os.unlink(lock_file_path)
                                except:
                                    pass
                except:
                    # Any error reading lock file, try to remove it
                    try:
                        os.unlink(lock_file_path)
                    except:
                        pass

        def acquire_lock():
            """Attempt to acquire the process lock."""
            try:
                # First check for existing process
                check_existing_process()
                
                # Create new lock file with our PID
                lock_file = open(lock_file_path, "w")
                lock_file.write(str(os.getpid()))
                lock_file.flush()
                os.fsync(lock_file.fileno())  # Ensure file is written to disk
                
                # Try to acquire exclusive lock
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return lock_file
            except (IOError, OSError) as e:
                # If we failed to acquire lock, double check process again
                check_existing_process()
                
                # If we get here, something else went wrong
                log(f"Failed to acquire lock: {e}")
                error_resp = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": "Failed to acquire bridge process lock"
                    },
                    "id": "0"
                }
                sys.stdout.write(json.dumps(error_resp) + "\n")
                sys.stdout.flush()
                sys.exit(1)

        # First acquire the lock before doing anything else
        lock_file = acquire_lock()
        log("Successfully acquired process lock")

        # Now that we have the lock, create log files with unique timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        pid = os.getpid()
        claude_stdin_log = open(log_dir / f"claude_stdin_{timestamp}_{pid}.log", "w", buffering=1)  # Line buffered
        claude_stdout_log = open(log_dir / f"claude_stdout_{timestamp}_{pid}.log", "w", buffering=1)  # Line buffered
        
        log(f"Opened Claude communication logs with timestamp {timestamp} and PID {pid}")

        # Immediate stdout test
        test_message = {
            "jsonrpc": "2.0",
            "method": "startup_test",
            "result": {"status": "Bridge starting up"},
            "id": "startup-test"
        }
        log("Testing immediate stdout write...")
        try:
            test_json = json.dumps(test_message)
            # Try direct stdout write first
            sys.stdout.write(test_json + "\n")
            sys.stdout.flush()
            log("Direct stdout write completed")
            
            # Also try buffer write
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout.buffer.write((test_json + "\n").encode('utf-8'))
                sys.stdout.buffer.flush()
                log("Buffer stdout write completed")
            
            # Log the test message
            log_claude_stdout(test_json)
            log("Test message logged to stdout log")
        except Exception as e:
            log(f"Immediate stdout test failed: {str(e)}")
            log(traceback.format_exc())

        def log_claude_stdin(data: str):
            """Log data received from Claude (stdin)."""
            try:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_entry = f"{timestamp} CLAUDE INPUT:\n{data}\n{'='*80}\n"
                claude_stdin_log.write(log_entry)
                claude_stdin_log.flush()
                os.fsync(claude_stdin_log.fileno())
                log(f"Logged {len(data)} bytes to stdin log")
            except Exception as e:
                log(f"Error logging Claude stdin: {e}")

        def log_claude_stdout(data: str):
            """Log data sent to Claude (stdout)."""
            try:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_entry = f"{timestamp} CLAUDE OUTPUT:\n{data}\n{'='*80}\n"
                claude_stdout_log.write(log_entry)
                claude_stdout_log.flush()
                os.fsync(claude_stdout_log.fileno())
                log(f"Logged {len(data)} bytes to stdout log")
            except Exception as e:
                log(f"Error logging Claude stdout: {e}")

        # Configure stdin for unbuffered operation
        try:
            # Set stdin to binary mode on Windows
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            
            # Set non-blocking mode on stdin
            orig_fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
            fcntl.fcntl(sys.stdin, fcntl.F_SETFL, orig_fl | os.O_NONBLOCK)
            
            # Force stdin to be unbuffered
            if hasattr(sys.stdin, 'buffer'):
                sys.stdin = io.TextIOWrapper(
                    sys.stdin.buffer,
                    encoding='utf-8',
                    errors='replace',
                    write_through=True,
                    line_buffering=True
                )
                log("Configured stdin for unbuffered operation")
                
                # Verify stdin configuration
                try:
                    log(f"Stdin buffering mode: {sys.stdin.buffer.raw.mode}, encoding: {sys.stdin.encoding}")
                    log(f"Stdin is a tty: {sys.stdin.isatty()}")
                    log(f"Stdin fileno: {sys.stdin.fileno()}")
                except Exception as e:
                    log(f"Error checking stdin configuration: {e}")
        except Exception as e:
            log(f"Error configuring stdin: {e}")
            log(traceback.format_exc())

        def read_from_stdin() -> Optional[str]:
            """Safely read a line from stdin with proper error handling."""
            log("=== STDIN READ BEGIN ===")
            try:
                log("Attempting to read from stdin...")
                line = sys.stdin.readline()
                log(f"Read completed, got {len(line) if line else 0} bytes")
                
                if not line:  # EOF detected
                    log("EOF detected on stdin (empty read). Claude has disconnected.")
                    return None
                
                stripped_line = line.strip()
                log(f"Raw line length: {len(line)}, Stripped line length: {len(stripped_line)}")
                
                if stripped_line:  # Only log non-empty lines
                    try:
                        # Try to parse as JSON to pretty print in logs
                        data = json.loads(stripped_line)
                        formatted_data = json.dumps(data, indent=2)
                        log_claude_stdin(formatted_data)
                        log(f"Successfully parsed JSON input: {data.get('method', 'unknown')} (id: {data.get('id', 'none')})")
                    except json.JSONDecodeError as e:
                        # If not valid JSON, log as is
                        log(f"Failed to parse JSON: {e}")
                        log_claude_stdin(stripped_line)
                    except Exception as e:
                        log(f"Error processing stdin data: {e}")
                else:
                    log("Empty line after stripping")
                
                log("=== STDIN READ END ===")
                return stripped_line
                
            except IOError as e:
                if e.errno == errno.EWOULDBLOCK:
                    log("Would block on stdin read, skipping")
                    return None
                log(f"IOError reading from stdin: {e}")
                return None
            except Exception as e:
                log(f"Unexpected error reading from stdin: {e}")
                log(traceback.format_exc())
                return None

        # Test stdin reading at startup
        try:
            log("Testing stdin reading...")
            # Check if stdin has data available
            if select.select([sys.stdin], [], [], 0.1)[0]:
                test_read = read_from_stdin()
                log(f"Stdin test read result: {test_read}")
            else:
                log("No data available on stdin during test")
        except Exception as e:
            log(f"Stdin test failed: {e}")
            log(traceback.format_exc())

        # Ensure stdout is properly configured for unbuffered operation
        if hasattr(sys.stdout, 'buffer'):
            # Force stdout to be unbuffered
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer,
                encoding='utf-8',
                errors='replace',
                write_through=True,
                buffering=0  # Force unbuffered
            )
            log("Configured stdout for unbuffered operation")
            
            # Verify stdout configuration
            try:
                log(f"Stdout buffering mode: {sys.stdout.buffer.raw.mode}, encoding: {sys.stdout.encoding}")
                log(f"Stdout is a tty: {sys.stdout.isatty()}")
                log(f"Stdout fileno: {sys.stdout.fileno()}")
            except Exception as e:
                log(f"Error checking stdout configuration: {e}")

        def write_to_stdout(data: str, context: str = "response"):
            """Write directly to stdout using raw file descriptor."""
            log(f"===== STDOUT WRITE BEGIN ({context}) =====")
            try:
                # First log what we're about to send
                log_claude_stdout(data)
                
                # Prepare data with newline and encode
                output = (data + "\n").encode('utf-8')
                output_len = len(output)
                log(f"Attempting to write {output_len} bytes to stdout")
                
                # Get raw file descriptor for stdout
                stdout_fd = 1  # stdout is always file descriptor 1
                
                # Write in chunks to avoid any buffering issues
                total_written = 0
                chunk_size = 4096  # Standard buffer size
                
                while total_written < output_len:
                    remaining = output_len - total_written
                    to_write = min(remaining, chunk_size)
                    chunk = output[total_written:total_written + to_write]
                    
                    try:
                        bytes_written = os.write(stdout_fd, chunk)
                        if bytes_written > 0:
                            total_written += bytes_written
                            log(f"Wrote {bytes_written} bytes to stdout (total: {total_written}/{output_len})")
                        else:
                            log(f"Write returned 0 bytes")
                            break
                    except OSError as e:
                        if e.errno == errno.EAGAIN:  # Would block
                            time.sleep(0.1)  # Brief pause before retry
                            continue
                        raise
                
                if total_written == output_len:
                    log(f"Successfully wrote all {output_len} bytes to stdout")
                    return True
                else:
                    log(f"Only wrote {total_written} of {output_len} bytes")
                    return False
                    
            except BrokenPipeError:
                log(f"Broken pipe when writing {context} to stdout")
                return False
            except OSError as e:
                if e.errno == errno.EPIPE:
                    log(f"Pipe error writing {context} to stdout")
                    return False
                log(f"OS error writing {context} to stdout: {str(e)}")
                return False
            except Exception as e:
                log(f"Error writing {context} to stdout: {str(e)}")
                log(traceback.format_exc())
                return False
            finally:
                log(f"===== STDOUT WRITE END ({context}) =====")

        # Test stdout writing with raw file descriptor
        test_message = {
            "jsonrpc": "2.0",
            "method": "test",
            "result": {"status": "Testing raw stdout write"},
            "id": "test-raw"
        }
        
        log("Testing raw stdout write...")
        try:
            test_json = json.dumps(test_message)
            if write_to_stdout(test_json, "startup test"):
                log("Raw stdout write test successful")
            else:
                log("Raw stdout write test failed")
        except Exception as e:
            log(f"Raw stdout write test error: {e}")
            log(traceback.format_exc())

        # Disable stdout buffering completely
        try:
            # Close any existing stdout wrapper
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout.buffer.raw.close()
            sys.stdout.close()
            
            # Open stdout as a raw file descriptor
            stdout_fd = os.open('/dev/stdout', os.O_WRONLY | os.O_NONBLOCK)
            # Don't wrap in TextIOWrapper to avoid any buffering
            os.dup2(stdout_fd, 1)  # Replace stdout (fd 1) with our raw fd
            log("Configured raw stdout file descriptor")
        except Exception as e:
            log(f"Error configuring raw stdout: {e}")
            log(traceback.format_exc())

        # Print startup message
        log(f"Starting MCP bridge in stdin/stdout mode (API key: {api_key[:5]}...)")
        log(f"Connecting to ws://{host}:{port}/api/bridge/connect")
        
        # Dictionary to track request IDs for async communication
        pending_requests = {}
        response_queue = []
        connection_id = None
        connection_initialized = False
        initialize_response_count = 0   # Count how many initialize responses we've received
        max_initialize_responses = 10   # Maximum number before taking drastic action
        last_connection_time = 0        # Track when we last established a connection
        connection_attempt_count = 0    # Track connection attempts
        broken_pipe_count = 0           # Track broken pipe errors
        max_broken_pipes = 3            # Maximum broken pipes before exiting
        active_connection = False       # Track whether we have an active connection
        connection_lock = threading.Lock()  # Lock to prevent concurrent connection attempts
        processed_response_ids = set()  # Track IDs of responses we've already processed
        sent_response_ids = set()       # Track IDs of responses already sent to stdout
        current_websocket = None        # Reference to current websocket
        
        # Function to handle WebSocket communication in a separate thread
        async def websocket_thread():
            import asyncio
            
            async def connect_and_process():
                nonlocal connection_id
                nonlocal connection_initialized
                nonlocal initialize_response_count
                nonlocal last_connection_time
                nonlocal connection_attempt_count
                nonlocal broken_pipe_count
                nonlocal active_connection
                nonlocal processed_response_ids
                nonlocal current_websocket
                
                url = f"ws://{host}:{port}/api/bridge/connect"
                headers = {"X-API-Key": api_key}
                
                log(f"Connecting to WebSocket at {url}")
                
                # Track connection failures to implement fallback strategies
                ws_failure_count = 0
                max_failures_before_fallback = 3
                
                try:
                    while True:  # Main connection loop
                        try:
                            with connection_lock:
                                if active_connection:
                                    log(f"Another active connection already exists, waiting...")
                                    await asyncio.sleep(5)
                                    continue  # Skip this iteration and try again

                            try:
                                # Only set active_connection after successful connection
                                async with websockets.client.connect(url, extra_headers=headers) as websocket:
                                    with connection_lock:
                                        # Mark that we have an active connection
                                        connection_attempt_count += 1
                                        last_connection_time = time.time()
                                        active_connection = True
                                        # Store reference to current websocket 
                                        current_websocket = websocket
                                    
                                    log("WebSocket connected")
                                    
                                    # Wait for connection established message
                                    msg = await websocket.recv()
                                    data = json.loads(msg)
                                    if data.get("result", {}).get("type") == "connection_established":
                                        connection_id = data.get("result", {}).get("connection_id")
                                        log(f"Connection established with ID: {connection_id}")
                                        # Add connection response to queue so it's processed by main thread
                                        # Create a unique ID for tracking
                                        conn_msg_id = f"connection-{connection_id}"
                                        if conn_msg_id not in processed_response_ids:
                                            response_queue.append(data)
                                            processed_response_ids.add(conn_msg_id)
                                        else:
                                            log(f"Skipping duplicate connection message for {connection_id}")
                                    
                                    # Process any initialize request immediately after connection
                                    # This ensures we send it exactly once per connection
                                    initialize_sent = False
                                    if not connection_initialized:
                                        # Check for initialize request
                                        for req_id, req_data in list(pending_requests.items()):
                                            if req_data.get("method") == "initialize":
                                                try:
                                                    log(f"Sending initialize request with ID {req_id} immediately after connection")
                                                    await websocket.send(json.dumps(req_data))
                                                    initialize_sent = True
                                                    log(f"Initialize request sent successfully")
                                                    # Don't remove from pending until we get a response
                                                except Exception as e:
                                                    log(f"Error sending initialize request: {str(e)}")
                                                    raise  # Re-raise to trigger reconnect
                                                break  # Only send one initialize request
                                    
                                    # Main processing loop
                                    while True:
                                        # Check for incoming messages first
                                        try:
                                            # Use wait_for with a timeout to prevent blocking indefinitely
                                            message = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                                            log(f"Received message from WebSocket: {message[:100]}...")
                                            
                                            try:
                                                response = json.loads(message)
                                                resp_id = response.get("id")
                                                log(f"Parsed response with ID: {resp_id}")
                                                
                                                # Special handling for initialize response
                                                if resp_id == 0 or resp_id == "0":
                                                    log(f"Processing initialize response")
                                                    # Create unique tracking ID
                                                    response_hash = hash(json.dumps(response))
                                                    init_msg_id = f"initialize-{response_hash}"
                                                    
                                                    if init_msg_id not in processed_response_ids:
                                                        log(f"Adding initialize response to queue (hash: {response_hash})")
                                                        response_queue.append(response)
                                                        connection_initialized = True
                                                        processed_response_ids.add(init_msg_id)
                                                        # Remove initialize request from pending
                                                        for key in list(pending_requests.keys()):
                                                            if pending_requests[key].get("method") == "initialize":
                                                                log(f"Removing initialize request from pending (key: {key})")
                                                                del pending_requests[key]
                                                    else:
                                                        log(f"Skipping duplicate initialize response (hash: {response_hash})")
                                                    continue
                                                
                                                # Handle other responses
                                                if resp_id is not None:
                                                    response_hash = hash(json.dumps(response))
                                                    response_id = f"response-{resp_id}-{response_hash}"
                                                    
                                                    if response_id not in processed_response_ids:
                                                        log(f"Adding response {resp_id} to queue (hash: {response_hash})")
                                                        response_queue.append(response)
                                                        processed_response_ids.add(response_id)
                                                        # Remove from pending if it exists
                                                        if str(resp_id) in pending_requests:
                                                            log(f"Removing request {resp_id} from pending")
                                                            del pending_requests[str(resp_id)]
                                                    else:
                                                        log(f"Skipping duplicate response {resp_id} (hash: {response_hash})")
                                                
                                            except json.JSONDecodeError:
                                                log(f"Received invalid JSON from WebSocket: {message}")
                                            except Exception as e:
                                                log(f"Error processing WebSocket message: {str(e)}")
                                                log(traceback.format_exc())
                                            
                                        except asyncio.TimeoutError:
                                            # No message received, continue to process pending requests
                                            pass
                                        except websockets.exceptions.ConnectionClosed:
                                            log("WebSocket connection closed")
                                            raise  # Re-raise to trigger reconnect
                                        except Exception as e:
                                            log(f"Error receiving WebSocket message: {str(e)}")
                                            log(traceback.format_exc())
                                            raise  # Re-raise to trigger reconnect
                                        
                                        # Process pending requests
                                        if pending_requests:
                                            req_id, req_data = next(iter(pending_requests.items()))
                                            try:
                                                log(f"Sending request {req_id} via WebSocket")
                                                await websocket.send(json.dumps(req_data))
                                                log(f"Request {req_id} sent successfully")
                                            except Exception as e:
                                                log(f"Error sending request {req_id}: {str(e)}")
                                                raise  # Re-raise to trigger reconnect
                                        
                                        # Small sleep to prevent tight loop
                                        await asyncio.sleep(0.01)

                            except websockets.exceptions.InvalidStatusCode as e:
                                log(f"Invalid status code connecting to WebSocket: {e}")
                                with connection_lock:
                                    active_connection = False
                                    current_websocket = None
                                await asyncio.sleep(5)  # Wait before retrying
                                continue
                            except Exception as e:
                                log(f"Error establishing WebSocket connection: {e}")
                                with connection_lock:
                                    active_connection = False
                                    current_websocket = None
                                await asyncio.sleep(5)  # Wait before retrying
                                continue

                        except json.JSONDecodeError as e:
                            log(f"Error decoding message: {str(e)}")
                            with connection_lock:
                                active_connection = False
                                current_websocket = None
                            await asyncio.sleep(5)  # Wait before reconnecting
                            continue  # Try to reconnect
                        except Exception as e:
                            log(f"Error in message processing: {str(e)}")
                            with connection_lock:
                                active_connection = False
                                current_websocket = None
                            raise  # Re-raise to trigger reconnect
                except Exception as e:
                    log(f"Error in message processing: {str(e)}")
                    with connection_lock:
                        active_connection = False
                        current_websocket = None
                    raise  # Re-raise to trigger reconnect
                finally:
                    # Ensure active_connection is always cleared on any error
                    with connection_lock:
                        active_connection = False
                    current_websocket = None
            
            async def handle_requests_via_http():
                """Fallback to handle pending requests via HTTP when WebSocket fails."""
                log("Handling pending requests via HTTP fallback")
                
                # Copy the pending requests to avoid modification during iteration
                requests_to_process = dict(pending_requests)
                
                if not requests_to_process:
                    log("No pending requests to process via HTTP")
                    return
                
                base_url = f"http://{host}:{port}/api/bridge"
                headers = {
                    "X-API-Key": api_key,
                    "Content-Type": "application/json"
                }
                
                for req_id, req_data in requests_to_process.items():
                    try:
                        method = req_data.get("method")
                        log(f"Processing request {req_id} (method: {method}) via HTTP")
                        
                        async with httpx.AsyncClient() as client:
                            if method == "initialize":
                                resp = await client.post(f"{base_url}/initialize", headers=headers, json=req_data)
                            elif "." in method:  # Method call
                                resp = await client.post(f"{base_url}/invoke", headers=headers, json=req_data)
                            else:
                                # Unknown method type
                                log(f"Unknown method type: {method}, skipping HTTP fallback")
                                continue
                            
                            if resp.status_code == 200:
                                result = resp.json()
                                log(f"HTTP fallback successful for request {req_id}")
                                
                                # Remove from pending requests and add to response queue
                                if req_id in pending_requests:
                                    del pending_requests[req_id]
                                response_queue.append(result)
                            else:
                                log(f"HTTP fallback failed for request {req_id}: {resp.status_code}")
                    except Exception as e:
                        log(f"Error processing request {req_id} via HTTP: {str(e)}")
            
            # Create a new event loop for this thread
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            
            try:
                new_loop.run_until_complete(connect_and_process())
            except Exception as e:
                log(f"WebSocket thread crashed: {str(e)}")
                log(traceback.format_exc())
            finally:
                new_loop.close()
        
        # Start WebSocket thread
        ws_thread = None  # Track the WebSocket thread
        
        def start_websocket_thread():
            nonlocal ws_thread
            with connection_lock:
                if ws_thread is not None and ws_thread.is_alive():
                    log("WebSocket thread already running")
                    return
                
                log("Starting WebSocket thread in 0.5 seconds...")
                time.sleep(0.5)  # Small delay to ensure all variables are initialized
                
                def run_websocket():
                    # Create a new event loop for this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        new_loop.run_until_complete(websocket_thread())
                    except Exception as e:
                        log(f"WebSocket thread crashed: {str(e)}")
                        log(traceback.format_exc())
                    finally:
                        new_loop.close()
                
                ws_thread = threading.Thread(target=run_websocket, daemon=True)
                ws_thread.start()
                log("WebSocket thread started")

        # Flag to indicate when to exit
        should_exit = False
        
        # Handle proper shutdown
        def cleanup_and_exit():
            """Clean up resources and exit gracefully."""
            log("Bridge is shutting down...")
            # Clear all pending requests
            pending_requests.clear()
            log("All pending requests cleared")
            time.sleep(1)  # Give threads a chance to see this
            log("Bridge shutdown complete")

        try:
            # Main stdin/stdout loop
            log("Ready to process messages. Waiting for input...")
            
            while not should_exit:
                # First, check if there are any responses to send to stdout
                if response_queue:
                    try:
                        log(f"Found {len(response_queue)} responses in queue to process")
                        response = response_queue.pop(0)
                        
                        # Log the full response for debugging
                        log(f"Processing response from queue: {json.dumps(response, indent=2)}")
                        
                        # Create a unique ID for tracking sent responses
                        resp_id = response.get("id")
                        response_json = json.dumps(response)
                        response_hash = hash(response_json)
                        resp_tracking_id = f"sent-{resp_id}-{response_hash}"
                        
                        # Check if we've already sent this response
                        if resp_tracking_id in sent_response_ids:
                            log(f"Skipping already sent response with ID {resp_id} (hash: {response_hash})")
                            continue
                            
                        log(f"Writing response to stdout: length={len(response_json)}")
                        log(f"Response ID: {resp_id}, hash: {response_hash}") 
                        log(f"Response start: {response_json[:50]}...")
                        log(f"Response end: ...{response_json[-50:] if len(response_json) > 50 else response_json}")
                        
                        # Try to write to stdout multiple times if needed
                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            if write_to_stdout(response_json, "response"):
                                # Success - mark as sent and reset broken pipe counter
                                sent_response_ids.add(resp_tracking_id)
                                broken_pipe_count = 0
                                log(f"Successfully wrote response {resp_id} to stdout")
                                break
                            else:
                                retry_count += 1
                                broken_pipe_count += 1
                                if broken_pipe_count >= max_broken_pipes:
                                    log(f"ERROR: Detected {broken_pipe_count} broken pipe errors. Claude appears to have disconnected. Exiting.")
                                    should_exit = True
                                    break
                                if retry_count < max_retries:
                                    log(f"Failed to write to stdout, retrying in 1 second (attempt {retry_count}/{max_retries})")
                                    time.sleep(1)  # Brief pause before retry
                        
                        if retry_count == max_retries:
                            log(f"Failed to write response to stdout after {max_retries} attempts")
                            # Put the response back in the queue to try again later
                            response_queue.insert(0, response)
                            time.sleep(1)  # Wait before next attempt
                            continue
                            
                        if should_exit:
                            break
                            
                    except Exception as e:
                        log(f"Error processing response from queue: {str(e)}")
                        log(traceback.format_exc())
                        # Put the response back in the queue to try again
                        response_queue.insert(0, response)
                        time.sleep(1)  # Wait before next attempt
                
                # Check if there's input available from stdin
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    # Read from stdin (usually a json string)
                    log("INPUT DETECTED from Claude - reading line...")
                    line = read_from_stdin()
                    if line is None:  # EOF or error
                        # Wait a bit for any pending responses before exiting
                        wait_start = time.time()
                        while time.time() - wait_start < 5:  # Wait up to 5 seconds
                            if response_queue:
                                log(f"Still have {len(response_queue)} responses to send before exiting")
                                break
                            time.sleep(0.1)
                        if not response_queue:
                            log("No pending responses, safe to exit")
                            should_exit = True
                            break
                        continue
                    
                    log(f"RAW INPUT: '{line[:50]}...{line[-50:] if len(line) > 50 else ''}' (length: {len(line)})")
                    
                    if not line:
                        log("Empty line received, skipping")
                        empty_line_count = empty_line_count + 1 if 'empty_line_count' in locals() else 1
                        if empty_line_count > 50:
                            log(f"WARNING: Received {empty_line_count} empty lines. Checking connection state...")
                            # Check for active websocket connections
                            if ws_thread is not None and not ws_thread.is_alive():
                                log("WebSocket thread is no longer running")
                                # Check if we have any pending responses before exiting
                                if not response_queue and not pending_requests:
                                    log("No pending requests or responses, safe to exit")
                                    should_exit = True
                                    break
                                else:
                                    log(f"Still have pending items (responses: {len(response_queue)}, requests: {len(pending_requests)})")
                            # Even if WebSocket is alive, after too many empty lines we should check state
                            if empty_line_count > 100:
                                log(f"WARNING: {empty_line_count} empty lines. Checking final state...")
                                # Only exit if we have no pending work
                                if not response_queue and not pending_requests:
                                    log("No pending work, safe to exit")
                                    should_exit = True
                                    break
                                else:
                                    log(f"Still have pending items (responses: {len(response_queue)}, requests: {len(pending_requests)})")
                        time.sleep(0.1)
                        continue
                    
                    # Reset empty line counter on valid input
                    empty_line_count = 0
                    
                    try:
                        # Parse the input as JSON
                        request = json.loads(line)
                        request_id = request.get("id")
                        method = request.get("method")
                        log(f"PARSED JSON Request ID: {request_id}, Method: {method}")
                        
                        # Special handling for initialize requests
                        if method == "initialize":
                            # Check if we already have an initialize request in pending or if we're already initialized
                            if connection_initialized:
                                log(f"Skipping duplicate initialize request - connection already initialized")
                                # Send success response immediately for duplicate initialize
                                success_resp = {
                                    "jsonrpc": "2.0",
                                    "result": {"type": "success"},
                                    "id": request_id
                                }
                                log(f"Sending immediate success response for duplicate initialize")
                                if not write_to_stdout(json.dumps(success_resp), "duplicate initialize response"):
                                    should_exit = True
                                    break
                                continue
                            
                            has_initialize = False
                            for _, req in pending_requests.items():
                                if req.get("method") == "initialize":
                                    has_initialize = True
                                    break
                            
                            if has_initialize:
                                log(f"Already have pending initialize request, skipping new one")
                                continue
                        
                        # Add to pending requests to be sent via WebSocket
                        if request_id is not None:
                            request_id_str = str(request_id)
                            pending_requests[request_id_str] = request
                            log(f"Added request {request_id_str} to pending queue (total pending: {len(pending_requests)})")
                        else:
                            log("Request has no ID, generating one")
                            new_id = str(len(pending_requests) + 1)
                            request["id"] = new_id
                            pending_requests[new_id] = request
                            log(f"Added request with generated ID {new_id} to pending queue (total pending: {len(pending_requests)})")
                        
                        # Start WebSocket thread if not already running
                        start_websocket_thread()
                            
                    except json.JSONDecodeError:
                        log(f"Invalid JSON input: {line}")
                        # Send error response for JSON parse error
                        error_resp = {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32700,
                                "message": "Parse error"
                            },
                            "id": None
                        }
                        if not write_to_stdout(json.dumps(error_resp), "JSON parse error"):
                            should_exit = True
                            break
                        
                    except Exception as e:
                        log(f"Error processing message: {str(e)}")
                        log(f"Exception traceback: {traceback.format_exc()}")
                        error_resp = {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": -32000,
                                "message": f"Internal error: {str(e)}"
                            },
                            "id": "0"
                        }
                        if not write_to_stdout(json.dumps(error_resp), "internal error"):
                            should_exit = True
                            break
                else:
                    # No input available, sleep a bit
                    time.sleep(0.1)
        
        except KeyboardInterrupt:
            log("Bridge stopped by user")
        except Exception as e:
            log(f"Bridge error: {str(e)}")
            log(traceback.format_exc())
        finally:
            # Call cleanup function before exiting
            cleanup_and_exit()
            # Close Claude communication log files
            claude_stdin_log.close()
            claude_stdout_log.close()
            # Release the lock file
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
                # Try to remove the lock file
                try:
                    os.unlink(lock_file_path)
                except:
                    pass
            except:
                pass

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