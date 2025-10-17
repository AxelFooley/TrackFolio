# Next.js API Proxy Infrastructure

This document describes the Next.js App Router API proxy infrastructure that enables runtime backend URL configuration for the TrackFolio portfolio tracker.

## Overview

The API proxy system consists of several components that work together to provide seamless backend connectivity across different environments (development, Docker, production):

1. **Dynamic Route Handler** (`/src/app/api/[...path]/route.ts`)
2. **Runtime Backend URL Detection** with multiple fallback strategies
3. **Health Check System** for backend availability
4. **Backend Health Utilities** for debugging and testing
5. **Health Check UI** at `/api-health` for diagnostics

## Architecture

### Route Handler (`/src/app/api/[...path]/route.ts`)

The route handler acts as a proxy between the frontend and backend services. Key features:

- **Dynamic Backend URL Detection**: Automatically finds the correct backend URL at runtime
- **Health Check Integration**: Tests backend availability before proxying requests
- **CORS Support**: Handles cross-origin requests properly
- **Multi-Format Support**: Works with JSON, form data, and file uploads
- **Error Handling**: Graceful error responses with proper HTTP status codes
- **Request Logging**: Detailed logging for debugging

### Backend URL Resolution Strategy

The proxy follows this priority order for backend URL detection:

1. **Runtime Environment Variable** (`BACKEND_API_URL`)
   - Set via environment variables at runtime
   - Highest priority for explicit configuration

2. **Docker Internal URL** (`http://backend:8000`)
   - Used when running in Docker environment
   - Automatically detected based on environment clues

3. **Localhost URL** (`http://localhost:8000`)
   - Fallback for development environments
   - Default when no other options are available

### Health Check System

- **Cached Results**: Health check results are cached for 30 seconds to avoid repeated requests
- **Timeout Protection**: 5-second timeout for health check requests
- **Parallel Testing**: Multiple backend URLs can be tested simultaneously
- **Fallback Logic**: System gracefully degrades when no healthy backend is found

## Usage

### Frontend API Client

The API client (`/src/lib/api.ts`) now uses the proxy route:

```typescript
// Before: Direct backend connection
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

// After: Proxy route
const API_BASE_URL = '/api';
```

All existing API calls continue to work unchanged - they're now routed through the Next.js API proxy.

### Environment Configuration

#### Docker Environment (Production)

```yaml
# docker-compose.yml
frontend:
  environment:
    BACKEND_API_URL: http://backend:8000  # Docker internal URL
    NODE_ENV: production
    DOCKER_ENV: true
```

#### Development Environment

```bash
# .env.local (optional)
BACKEND_API_URL=http://localhost:8000
NODE_ENV=development
```

### Health Check Utilities

The `/src/lib/backend-health.ts` provides utilities for testing backend connectivity:

```typescript
import { findHealthyBackend, runBackendDiagnostics } from '@/lib/backend-health';

// Quick health check
const healthyBackend = await findHealthyBackend();

// Comprehensive diagnostics
const diagnostics = await runBackendDiagnostics();
```

### Health Check UI

Visit `/api-health` in your browser to:
- View current environment configuration
- Test backend URL candidates
- Verify API proxy functionality
- Get troubleshooting recommendations

## API Endpoint Support

The proxy supports all backend API endpoints:

### Traditional Portfolio APIs
- `/api/portfolio/overview` - Portfolio overview and metrics
- `/api/portfolio/holdings` - Current holdings
- `/api/portfolio/performance` - Historical performance data
- `/api/transactions/*` - Transaction management
- `/api/assets/*` - Asset information and prices
- `/api/prices/*` - Price management and updates
- `/api/benchmark` - Benchmark configuration

### Crypto Portfolio APIs
- `/api/crypto/portfolios/*` - Crypto portfolio management
- `/api/crypto/prices/*` - Crypto price data
- `/api/crypto/search` - Asset search
- `/api/blockchain/*` - Blockchain and wallet integration

## Error Handling

### Proxy Errors

The proxy returns structured error responses:

```json
{
  "error": "Backend request failed",
  "details": "Connection timeout",
  "backend_url": "http://backend:8000"
}
```

### Common Error Scenarios

1. **Backend Unavailable** (502 Bad Gateway)
   - Backend service is not running
   - Network connectivity issues
   - Backend health check failures

2. **Request Timeout** (504 Gateway Timeout)
   - Backend took too long to respond
   - Request exceeded 60-second timeout

3. **Invalid Request** (400 Bad Request)
   - Malformed JSON or form data
   - Invalid request format

## Monitoring and Debugging

### Request Logging

The proxy logs detailed information for each request:

```
[API Proxy] 2024-01-15T10:30:00.000Z GET /api/portfolio/overview
[API Proxy] Backend: http://backend:8000
[API Proxy] URL: http://localhost:3000/api/portfolio/overview
[API Proxy] User-Agent: Mozilla/5.0...
```

### Health Check Monitoring

- Health check results are cached to improve performance
- Failed health checks are logged with error details
- Backend URL selection is logged for debugging

## Configuration Options

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `BACKEND_API_URL` | Explicit backend URL | None | `http://backend:8000` |
| `NODE_ENV` | Environment type | `development` | `production` |
| `DOCKER_ENV` | Docker environment flag | `undefined` | `true` |

### Route Handler Configuration

```typescript
// Health check cache TTL (milliseconds)
const HEALTH_CHECK_CACHE_TTL = 30 * 1000; // 30 seconds

// Request timeout (milliseconds)
const REQUEST_TIMEOUT = 60 * 1000; // 60 seconds

// Health check timeout (milliseconds)
const HEALTH_CHECK_TIMEOUT = 5 * 1000; // 5 seconds
```

## Security Considerations

### CORS Configuration

- Development: Allows all origins (`*`)
- Production: Restricts to specific origins
- Supports credentials for authenticated requests

### Header Filtering

Problematic headers are filtered out when proxying:
- `host`, `connection`
- `content-length`, `transfer-encoding`
- `expect`, `upgrade`
- `proxy-authorization`

### Forwarded Headers

The proxy adds proper forwarded headers:
- `X-Forwarded-Host`
- `X-Forwarded-Proto`
- `X-Forwarded-For`
- `X-Real-IP`

## Troubleshooting

### Common Issues

1. **API calls failing with 502 errors**
   - Check if backend service is running
   - Verify Docker network connectivity
   - Use `/api-health` page for diagnostics

2. **CORS errors in browser**
   - Verify CORS headers in proxy response
   - Check allowed origins configuration
   - Ensure preflight OPTIONS requests are handled

3. **Slow response times**
   - Check backend health check cache TTL
   - Monitor backend response times
   - Consider adjusting timeout values

### Debug Steps

1. Visit `/api-health` page
2. Check environment configuration
3. Test backend URL candidates
4. Verify API proxy functionality
5. Review proxy logs in console

## Migration Notes

### From Direct Backend Connection

**Before:**
```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
```

**After:**
```typescript
const API_BASE_URL = '/api';
```

### Next.js Configuration

**Before:**
```javascript
async rewrites() {
  return [
    {
      source: '/api/:path*',
      destination: `${(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '')}/api/:path*`,
    },
  ];
}
```

**After:**
```javascript
// No rewrites needed - API routes handle proxying
```

## Benefits

1. **Environment Flexibility**: Works seamlessly across development, Docker, and production environments
2. **Runtime Configuration**: Backend URL can be changed without rebuilding the frontend
3. **Health Monitoring**: Automatic backend health checking with graceful fallbacks
4. **Better Debugging**: Comprehensive logging and health check UI
5. **CORS Handling**: Proper cross-origin request support
6. **Error Resilience**: Graceful error handling with meaningful responses
7. **Zero Breaking Changes**: Existing API calls continue to work unchanged