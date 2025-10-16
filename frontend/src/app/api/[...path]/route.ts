import { NextRequest, NextResponse } from 'next/server';
import { headers } from 'next/headers';

// Interface for backend health check response
interface HealthCheckResponse {
  status: string;
  timestamp?: string;
}

// Interface for error responses
interface ErrorResponse {
  error: string;
  details?: string;
  backend_url?: string;
}

// Cache for backend URL to avoid repeated health checks
let backendUrlCache: string | null = null;
let healthCheckCache: { url: string; timestamp: number; healthy: boolean } | null = null;
const HEALTH_CHECK_CACHE_TTL = 30 * 1000; // 30 seconds

/**
 * Get the runtime backend URL with fallback logic
 * Priority:
 * 1. BACKEND_API_URL environment variable (runtime)
 * 2. Docker internal URL (http://backend:8000) for production
 * 3. localhost URL (http://localhost:8000) for development
 */
async function getBackendUrl(): Promise<string> {
  // Return cached URL if available
  if (backendUrlCache) {
    return backendUrlCache;
  }

  // Check explicit runtime environment variable first
  const runtimeBackendUrl = process.env.BACKEND_API_URL;
  if (runtimeBackendUrl) {
    console.log(`[API Proxy] Using runtime BACKEND_API_URL: ${runtimeBackendUrl}`);
    backendUrlCache = runtimeBackendUrl;
    return runtimeBackendUrl;
  }

  // Detect environment
  const isDevelopment = process.env.NODE_ENV === 'development';
  const isDockerEnvironment = process.env.DOCKER_ENV === 'true' ||
                              process.cwd().includes('/app/') ||
                              !process.cwd().startsWith('/Users/');

  console.log(`[API Proxy] Environment detection:`, {
    NODE_ENV: process.env.NODE_ENV,
    DOCKER_ENV: process.env.DOCKER_ENV,
    isDevelopment,
    isDockerEnvironment,
    cwd: process.cwd()
  });

  // Determine candidate URLs
  const candidates = [
    ...(isDockerEnvironment ? ['http://backend:8000'] : []),
    'http://localhost:8000',
  ];

  console.log(`[API Proxy] Testing backend URL candidates:`, candidates);

  // Test each candidate URL
  for (const candidate of candidates) {
    if (await isBackendHealthy(candidate)) {
      console.log(`[API Proxy] Backend healthy at: ${candidate}`);
      backendUrlCache = candidate;
      return candidate;
    }
    console.log(`[API Proxy] Backend unhealthy at: ${candidate}`);
  }

  // If no healthy backend found, use default and let errors surface naturally
  const fallbackUrl = isDockerEnvironment ? 'http://backend:8000' : 'http://localhost:8000';
  console.warn(`[API Proxy] No healthy backend found, using fallback: ${fallbackUrl}`);
  backendUrlCache = fallbackUrl;
  return fallbackUrl;
}

/**
 * Check if backend is healthy with caching
 */
async function isBackendHealthy(url: string): Promise<boolean> {
  const now = Date.now();

  // Check cache first
  if (healthCheckCache &&
      healthCheckCache.url === url &&
      (now - healthCheckCache.timestamp) < HEALTH_CHECK_CACHE_TTL) {
    return healthCheckCache.healthy;
  }

  try {
    const healthUrl = `${url.replace(/\/+$/, '')}/api/health`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

    const response = await fetch(healthUrl, {
      method: 'GET',
      signal: controller.signal,
      headers: {
        'User-Agent': 'NextJS-API-Proxy/1.0',
      },
    });

    clearTimeout(timeoutId);

    const isHealthy = response.ok;

    // Cache the result
    healthCheckCache = {
      url,
      timestamp: now,
      healthy: isHealthy,
    };

    return isHealthy;
  } catch (error) {
    console.warn(`[API Proxy] Health check failed for ${url}:`, error instanceof Error ? error.message : error);

    // Cache failed health check
    healthCheckCache = {
      url,
      timestamp: now,
      healthy: false,
    };

    return false;
  }
}

/**
 * Check if a URL should be excluded from proxying
 */
function shouldExcludeUrl(pathname: string): boolean {
  const excludePatterns = [
    '/_next',
    '/favicon',
    '/robots.txt',
    '/sitemap.xml',
    '/api/health', // Let Next.js handle its own health checks
  ];

  return excludePatterns.some(pattern => pathname.startsWith(pattern));
}

/**
 * Copy headers from incoming request to outgoing request
 */
function copyHeaders(source: Headers, target: HeadersInit): HeadersInit {
  const headers = new Headers(target);

  // Copy all headers except problematic ones
  const excludeHeaders = [
    'host',
    'connection',
    'content-length',
    'transfer-encoding',
    'expect',
    'upgrade',
    'proxy-authorization',
  ];

  source.forEach((value, key) => {
    const lowerKey = key.toLowerCase();
    if (!excludeHeaders.includes(lowerKey)) {
      headers.set(key, value);
    }
  });

  return headers;
}

/**
 * Handle CORS headers
 */
function addCorsHeaders(response: NextResponse, origin?: string): NextResponse {
  // Allow all origins in development, be more restrictive in production
  const allowedOrigins = process.env.NODE_ENV === 'development'
    ? ['*']
    : ['http://localhost:3000', 'http://127.0.0.1:3000'];

  if (origin && (allowedOrigins.includes('*') || allowedOrigins.includes(origin))) {
    response.headers.set('Access-Control-Allow-Origin', origin);
  } else if (allowedOrigins.includes('*')) {
    response.headers.set('Access-Control-Allow-Origin', '*');
  }

  response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, PATCH, OPTIONS');
  response.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept, Origin');
  response.headers.set('Access-Control-Allow-Credentials', 'true');
  response.headers.set('Access-Control-Max-Age', '86400'); // 24 hours

  return response;
}

/**
 * Log request details for debugging
 */
function logRequest(request: NextRequest, backendUrl: string, pathname: string): void {
  const timestamp = new Date().toISOString();
  const method = request.method;
  const url = request.url;
  const userAgent = request.headers.get('user-agent') || 'unknown';
  const referer = request.headers.get('referer') || 'none';
  const xForwardedFor = request.headers.get('x-forwarded-for') || 'none';

  console.log(`[API Proxy] ${timestamp} ${method} ${pathname}`);
  console.log(`[API Proxy] Backend: ${backendUrl}`);
  console.log(`[API Proxy] URL: ${url}`);
  console.log(`[API Proxy] User-Agent: ${userAgent}`);
  console.log(`[API Proxy] Referer: ${referer}`);
  console.log(`[API Proxy] X-Forwarded-For: ${xForwardedFor}`);
}

/**
 * Create error response with proper formatting
 */
function createErrorResponse(
  status: number,
  message: string,
  details?: string,
  backendUrl?: string
): NextResponse {
  const errorResponse: ErrorResponse = {
    error: message,
    ...(details && { details }),
    ...(backendUrl && { backend_url: backendUrl }),
  };

  const response = NextResponse.json(errorResponse, { status });
  response.headers.set('Content-Type', 'application/json');

  return addCorsHeaders(response);
}

/**
 * Handle OPTIONS requests for CORS preflight
 */
function handleOptionsRequest(request: NextRequest): NextResponse {
  const response = new NextResponse(null, { status: 200 });
  return addCorsHeaders(response, request.headers.get('origin') || undefined);
}

/**
 * Main route handler for API proxy
 */
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const params = await context.params;
  return handleRequest(request, params);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const params = await context.params;
  return handleRequest(request, params);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const params = await context.params;
  return handleRequest(request, params);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const params = await context.params;
  return handleRequest(request, params);
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  const params = await context.params;
  return handleRequest(request, params);
}

export async function OPTIONS(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
): Promise<NextResponse> {
  return handleOptionsRequest(request);
}

/**
 * Unified request handler for all HTTP methods
 */
async function handleRequest(
  request: NextRequest,
  params: { path: string[] }
): Promise<NextResponse> {
  const pathname = `/api/${params.path?.join('/') || ''}`;

  // Handle CORS preflight
  if (request.method === 'OPTIONS') {
    return handleOptionsRequest(request);
  }

  // Skip excluded URLs
  if (shouldExcludeUrl(pathname)) {
    console.log(`[API Proxy] Skipping excluded URL: ${pathname}`);
    return createErrorResponse(404, 'Not Found', 'URL excluded from proxy');
  }

  try {
    // Get the backend URL
    const backendUrl = await getBackendUrl();

    // Log the request for debugging
    logRequest(request, backendUrl, pathname);

    // Construct the target URL
    const targetUrl = `${backendUrl.replace(/\/+$/, '')}${pathname}`;
    const url = new URL(targetUrl);

    // Copy query parameters from original request
    request.nextUrl.searchParams.forEach((value, key) => {
      url.searchParams.set(key, value);
    });

    // Prepare headers
    const requestHeaders = copyHeaders(request.headers, {
      'X-Forwarded-Host': request.headers.get('host') || '',
      'X-Forwarded-Proto': request.nextUrl.protocol,
      'X-Forwarded-For': request.headers.get('x-forwarded-for') || request.ip || '',
      'X-Real-IP': request.ip || '',
    });

    // Prepare request options
    const requestOptions: RequestInit = {
      method: request.method,
      headers: requestHeaders,
    };

    // Handle request body
    const contentType = request.headers.get('content-type');
    if (contentType && ['POST', 'PUT', 'PATCH'].includes(request.method)) {
      if (contentType.includes('application/json')) {
        try {
          const body = await request.text();
          requestOptions.body = body;
          (requestHeaders as Record<string, string>)['Content-Type'] = 'application/json';
        } catch (error) {
          console.error('[API Proxy] Failed to read JSON body:', error);
          return createErrorResponse(400, 'Bad Request', 'Invalid JSON body');
        }
      } else if (contentType.includes('multipart/form-data') || contentType.includes('application/x-www-form-urlencoded')) {
        try {
          const body = await request.arrayBuffer();
          requestOptions.body = body;
          // Content-Type will be set automatically with boundary for multipart/form-data
        } catch (error) {
          console.error('[API Proxy] Failed to read form data:', error);
          return createErrorResponse(400, 'Bad Request', 'Invalid form data');
        }
      } else {
        // For other content types, pass through the body
        try {
          const body = await request.arrayBuffer();
          requestOptions.body = body;
        } catch (error) {
          console.error('[API Proxy] Failed to read request body:', error);
          return createErrorResponse(400, 'Bad Request', 'Failed to read request body');
        }
      }
    }

    console.log(`[API Proxy] Forwarding ${request.method} request to:`, url.toString());

    // Make the backend request with timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout

    try {
      const backendResponse = await fetch(url.toString(), {
        ...requestOptions,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Prepare response headers
      const responseHeaders = new Headers();

      // Copy backend response headers
      backendResponse.headers.forEach((value, key) => {
        // Skip problematic headers
        const lowerKey = key.toLowerCase();
        if (!['connection', 'transfer-encoding', 'content-encoding'].includes(lowerKey)) {
          responseHeaders.set(key, value);
        }
      });

      // Create response with appropriate body
      let responseBody: ReadableStream | string | null = null;
      const contentType = backendResponse.headers.get('content-type') || '';

      if (contentType.includes('application/json')) {
        try {
          const jsonData = await backendResponse.json();
          responseBody = JSON.stringify(jsonData);
          responseHeaders.set('Content-Type', 'application/json');
        } catch (error) {
          console.warn('[API Proxy] Failed to parse JSON response:', error);
          // If JSON parsing fails, return text
          responseBody = await backendResponse.text();
          responseHeaders.set('Content-Type', 'text/plain');
        }
      } else {
        // Stream non-JSON responses
        responseBody = backendResponse.body;
      }

      const response = new NextResponse(responseBody, {
        status: backendResponse.status,
        statusText: backendResponse.statusText,
        headers: responseHeaders,
      });

      // Add CORS headers
      const origin = request.headers.get('origin') || undefined;
      return addCorsHeaders(response, origin);

    } catch (fetchError) {
      clearTimeout(timeoutId);

      if (fetchError instanceof Error && fetchError.name === 'AbortError') {
        console.error('[API Proxy] Request timeout for:', url.toString());
        return createErrorResponse(504, 'Gateway Timeout', 'Backend request timed out', backendUrl);
      }

      console.error('[API Proxy] Backend request failed:', fetchError);
      return createErrorResponse(502, 'Bad Gateway', 'Backend request failed', backendUrl);
    }

  } catch (error) {
    console.error('[API Proxy] Unexpected error:', error);
    return createErrorResponse(
      500,
      'Internal Server Error',
      error instanceof Error ? error.message : 'Unknown error'
    );
  }
}

/**
 * Route segment config for dynamic params
 */
export const dynamic = 'force-dynamic';
export const revalidate = 0;