# MCP Gateway

A Python-based gateway server implementing the Model Context Protocol (MCP) for managing and routing AI tools on your local system.

## Development Roadmap

### Phase 1: Core Infrastructure (Current)
- Basic FastAPI server setup with health check
- API key and app management
- Modern React/Vite admin interface
- Connection monitoring and debugging UI

### Phase 2: MCP Implementation (Next)
- Minimal MCP server implementation with JSON-RPC over stdio
- Basic authentication with API keys
- Proof of concept: Direct connection from Claude/Cursor using built-in tools
- Debug/monitoring features in admin UI

### Phase 3: Tool Registration (Planned)
- Tool registration API
- MCP client implementation for tool discovery
- Capability negotiation and routing
- Extended admin interface for tool management

### Phase 4: Advanced Features (Future)
- WebSocket/SSE support
- Resource and prompt management
- Sampling capabilities
- Enhanced security and monitoring

## Installation

### For Users

Simply install using pip:

```bash
pip install mcp-gateway
```

The package includes a pre-built admin interface. No additional dependencies (like Node.js) are required.

### For Developers

1. Clone the repository
2. Install Python dependencies:
```bash
pip install -e .
```

3. (Optional) To modify the admin interface:
   - Install Node.js
   - Navigate to frontend directory: `cd frontend`
   - Install dependencies: `npm install`
   - Start development server: `npm run dev`

The frontend will be automatically built and included in the Python package during installation.

## Usage

### Starting the Gateway Server

For production use, start the MCP Gateway server:

```bash
mcp-gateway serve
```

For development with hot-reloading frontend and backend:

```bash
mcp-gateway dev
```

The admin interface will be available at:
- Production: http://localhost:8000
- Development: http://localhost:5173 (frontend) and http://localhost:8000 (backend API)

Files are stored following the XDG Base Directory Specification:

Data (SQLite database, etc):
- Linux: `$XDG_DATA_HOME/mcp-gateway/` (defaults to `~/.local/share/mcp-gateway/`)
- macOS: `~/Library/Application Support/mcp-gateway/`
- Windows: `%APPDATA%\mcp-gateway\`

Configuration:
- Linux: `$XDG_CONFIG_HOME/mcp-gateway/` (defaults to `~/.config/mcp-gateway/`)
- macOS: `~/Library/Application Support/mcp-gateway/`
- Windows: `%APPDATA%\mcp-gateway\`

Cache:
- Linux: `$XDG_CACHE_HOME/mcp-gateway/` (defaults to `~/.cache/mcp-gateway/`)
- macOS: `~/Library/Caches/mcp-gateway/`
- Windows: `%LOCALAPPDATA%\mcp-gateway\`

### Managing Connections

Create a new app:

```bash
mcp-gateway create-app "My App" --description "My MCP-enabled application"
```

Create an API key for an app:

```bash
mcp-gateway create-key "My Key" APP_ID
```

List registered apps and keys:

```bash
mcp-gateway list-apps
mcp-gateway list-keys
```

### Using as an MCP Tool

To expose a tool through the MCP gateway:

```bash
mcp-gateway bridge APP_ID
```

This creates a stdio bridge that can be used in tool configurations for Claude, Cursor, or other MCP-compatible agents.

Example tool configuration:
```json
{
  "name": "my_tool",
  "command": "mcp-gateway bridge my-app-id",
  "transport": "stdio"
}
```

## Development

The project uses modern Python tools and practices:

- FastAPI for the admin API
- SQLAlchemy for database management
- Typer for CLI interface
- JSON-RPC 2.0 for MCP communication
- React/Vite for the admin interface (pre-built and included in package)

### Project Structure

```
mcp-gateway/
├── src/
│   └── mcp_gateway/
│       ├── api/         # FastAPI routes
│       ├── models/      # SQLAlchemy models
│       ├── services/    # Business logic
│       └── static/      # Built frontend files
├── frontend/           # React frontend source
└── scripts/           # Build and utility scripts
```

### Testing

The project uses Playwright for end-to-end testing of the admin interface. To run the tests:

```bash
cd frontend
npm test
```

Note: Tests are designed to run in isolation and will mock all necessary API responses. Each test should:
- Mock all required API endpoints
- Start from a clean state
- Not depend on previous test runs or existing data
- Clean up any created resources

When writing new tests, ensure they follow these principles to maintain reliability and reproducibility.

## Contributing

This project implements the Model Context Protocol (MCP). For more information about the protocol, see the [MCP Specification](https://spec.modelcontextprotocol.io/).

## License

MIT License