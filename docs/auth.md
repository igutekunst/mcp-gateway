# MCP Gateway Authentication

## Overview
MCP Gateway requires different authentication mechanisms for different types of access:
1. Admin UI access (web interface)
2. Tool Provider connections
3. Agent connections

## Authentication Types

### Admin UI Authentication
- Uses session-based authentication with HTTP-only cookies
- Sessions are time-limited (1 hour by default)
- Admin password is required for initial setup
- All admin API endpoints require valid session

Flow:
1. Admin logs in with password
2. Server validates password and creates session
3. Session token stored in HTTP-only cookie
4. Frontend includes cookie in all admin requests
5. Server validates session token for admin endpoints

### Tool Provider Authentication
- Continues to use API key system
- API keys are scoped to specific tool providers
- Keys must be included in `X-API-Key` header
- Limited to tool-specific endpoints

### Agent Authentication
- Uses same API key system as tool providers
- Keys are scoped to specific agents
- Different permission set from tool providers
- Keys must be included in `X-API-Key` header

## Security Considerations

### Local Development
- Even in development, authentication is required
- No special trust for localhost connections
- HTTPS recommended but optional for local development
- Warning displayed when running without HTTPS

### Production Deployment
- HTTPS required by default
- Strict cookie settings (Secure, HttpOnly, SameSite)
- Session expiration and renewal
- Rate limiting on login attempts

## Configuration

### Environment Variables
```env
MCP_ADMIN_PASSWORD_HASH=<hashed_password>  # Set via CLI command
MCP_COOKIE_SECRET=<random_secret>          # Auto-generated if not provided
MCP_ALLOW_INSECURE=false                   # Set to true for HTTP in development
MCP_SESSION_EXPIRE_MINUTES=60              # Session duration in minutes
```

### Cookie Settings
```python
cookie_settings = {
    "httponly": True,
    "secure": not settings.ALLOW_INSECURE,
    "samesite": "strict",
    "max_age": settings.SESSION_EXPIRE_MINUTES * 60
}
```

## Implementation Plan

### Phase 1: Admin Authentication
1. ✓ Add admin password configuration
   - Created settings module with password handling
   - Added CLI command for password management
   - Implemented secure password hashing
   - Added environment variable support
2. Implement session management (In Progress)
3. Add login endpoint
4. Update frontend with authentication flow
5. Protect admin routes

### Phase 2: Enhanced Tool/Agent Auth
1. Review existing API key system
2. Add key scoping and permissions
3. Implement key rotation
4. Add usage monitoring

### Phase 3: Security Hardening
1. Add HTTPS enforcement
2. Implement rate limiting
3. Add session renewal
4. Add security headers

## API Endpoints

### Admin Authentication
```
POST /api/auth/admin/login
- Request: { "password": string }
- Response: { "expires_at": string }
- Sets HTTP-only session cookie

POST /api/auth/admin/logout
- Clears session cookie

GET /api/auth/admin/session
- Returns current session status
```

### API Key Management (Requires Admin Session)
```
GET /api/auth/keys
POST /api/auth/keys
DELETE /api/auth/keys/{key_id}
```

## CLI Commands

### Admin Password Management
```bash
# Set or update admin password
mcp-gateway set-admin-password

# The command will:
# - Prompt for password with confirmation
# - Hash the password securely
# - Store in .env file
# - Update running configuration
```

## Implementation Progress

### Completed
- ✓ Settings module with password configuration
- ✓ Password hashing and verification
- ✓ CLI command for password management
- ✓ Environment variable handling
- ✓ Admin authentication schemas

### In Progress
- Session management implementation
- Database schema for sessions
- Session token generation and validation

### Pending
- Login endpoint implementation
- Frontend authentication flow
- Route protection middleware
- Session renewal mechanism