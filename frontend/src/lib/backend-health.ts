/**
 * Backend health check utilities
 * Useful for debugging and testing backend connectivity
 */

export interface BackendHealthStatus {
  url: string;
  healthy: boolean;
  responseTime?: number;
  error?: string;
  timestamp: string;
}

export interface HealthCheckOptions {
  timeout?: number;
  retries?: number;
}

/**
 * Check health of a specific backend URL
 */
export async function checkBackendHealth(
  url: string,
  options: HealthCheckOptions = {}
): Promise<BackendHealthStatus> {
  const { timeout = 5000, retries = 1 } = options;
  const startTime = Date.now();
  const timestamp = new Date().toISOString();

  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const healthUrl = `${url.replace(/\/+$/, '')}/api/health`;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(healthUrl, {
        method: 'GET',
        signal: controller.signal,
        headers: {
          'User-Agent': 'TrackFolio-Frontend/1.0',
        },
      });

      clearTimeout(timeoutId);

      const responseTime = Date.now() - startTime;

      if (response.ok) {
        return {
          url,
          healthy: true,
          responseTime,
          timestamp,
        };
      } else {
        return {
          url,
          healthy: false,
          responseTime,
          error: `HTTP ${response.status}: ${response.statusText}`,
          timestamp,
        };
      }
    } catch (error) {
      if (attempt === retries) {
        const responseTime = Date.now() - startTime;
        return {
          url,
          healthy: false,
          responseTime,
          error: error instanceof Error ? error.message : 'Unknown error',
          timestamp,
        };
      }
      // Wait before retry
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }

  return {
    url,
    healthy: false,
    timestamp,
  };
}

/**
 * Check health of multiple backend URLs in parallel
 */
export async function checkMultipleBackendHealth(
  urls: string[],
  options: HealthCheckOptions = {}
): Promise<BackendHealthStatus[]> {
  const promises = urls.map(url => checkBackendHealth(url, options));
  return Promise.all(promises);
}

/**
 * Get candidate backend URLs based on environment
 */
export function getBackendCandidates(): string[] {
  const candidates: string[] = [];

  // Check for explicit runtime configuration
  if (typeof process !== 'undefined' && process.env?.BACKEND_API_URL) {
    candidates.push(process.env.BACKEND_API_URL);
  }

  // Check environment
  const isDevelopment = process?.env?.NODE_ENV === 'development';
  const isDockerEnvironment = process?.env?.DOCKER_ENV === 'true' ||
                              (typeof process !== 'undefined' && process.cwd().includes('/app/')) ||
                              (typeof process !== 'undefined' && !process.cwd().startsWith('/Users/'));

  if (isDockerEnvironment) {
    candidates.push('http://backend:8000');
  }

  // Always add localhost as fallback
  candidates.push('http://localhost:8000');

  // Add more candidates for development
  if (isDevelopment) {
    candidates.push('http://127.0.0.1:8000');
  }

  return Array.from(new Set(candidates)); // Remove duplicates
}

/**
 * Find the first healthy backend URL
 */
export async function findHealthyBackend(
  options: HealthCheckOptions = {}
): Promise<BackendHealthStatus | null> {
  const candidates = getBackendCandidates();
  console.log('[Backend Health] Testing candidates:', candidates);

  const results = await checkMultipleBackendHealth(candidates, options);

  // Sort by health and response time
  const healthyResults = results
    .filter(result => result.healthy)
    .sort((a, b) => (a.responseTime || Infinity) - (b.responseTime || Infinity));

  if (healthyResults.length > 0) {
    console.log('[Backend Health] First healthy backend:', healthyResults[0]);
    return healthyResults[0];
  }

  console.log('[Backend Health] No healthy backends found');
  return null;
}

/**
 * Test the API proxy route
 */
export async function testApiProxy(): Promise<{
  working: boolean;
  error?: string;
  backendUrl?: string;
}> {
  try {
    const response = await fetch('/api/health', {
      method: 'GET',
      headers: {
        'User-Agent': 'TrackFolio-Frontend/1.0',
      },
    });

    if (response.ok) {
      const data = await response.json();
      return {
        working: true,
        backendUrl: data.backend_url || 'Unknown',
      };
    } else {
      return {
        working: false,
        error: `HTTP ${response.status}: ${response.statusText}`,
      };
    }
  } catch (error) {
    return {
      working: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

/**
 * Run comprehensive backend diagnostics
 */
export async function runBackendDiagnostics(): Promise<{
  timestamp: string;
  environment: {
    NODE_ENV: string;
    DOCKER_ENV?: string;
    BACKEND_API_URL?: string;
    isDockerEnvironment: boolean;
  };
  candidates: BackendHealthStatus[];
  proxyTest: {
    working: boolean;
    error?: string;
    backendUrl?: string;
  };
  recommendations: string[];
}> {
  const timestamp = new Date().toISOString();

  // Environment info
  const environment = {
    NODE_ENV: process.env?.NODE_ENV || 'unknown',
    DOCKER_ENV: process.env?.DOCKER_ENV,
    BACKEND_API_URL: process.env?.BACKEND_API_URL,
    isDockerEnvironment: process.env?.DOCKER_ENV === 'true' ||
                        process.cwd().includes('/app/') ||
                        !process.cwd().startsWith('/Users/'),
  };

  // Test candidates
  const candidates = await checkMultipleBackendHealth(getBackendCandidates());

  // Test proxy
  const proxyTest = await testApiProxy();

  // Generate recommendations
  const recommendations: string[] = [];

  const healthyCount = candidates.filter(c => c.healthy).length;
  if (healthyCount === 0) {
    recommendations.push('No healthy backend URLs found. Check if the backend service is running.');
    recommendations.push('Ensure Docker containers are started with: docker compose up --build');
  } else if (healthyCount > 1) {
    recommendations.push('Multiple healthy backends found. Consider setting BACKEND_API_URL environment variable for consistency.');
  }

  if (!proxyTest.working) {
    recommendations.push('API proxy test failed. Check Next.js API route configuration.');
    recommendations.push('Verify the route handler exists at /src/app/api/[...path]/route.ts');
  }

  if (environment.isDockerEnvironment && !candidates.some(c => c.url.includes('backend:8000') && c.healthy)) {
    recommendations.push('Docker environment detected but backend:8000 is not healthy. Check Docker network configuration.');
  }

  if (!environment.isDockerEnvironment && !candidates.some(c => c.url.includes('localhost') && c.healthy)) {
    recommendations.push('Development environment detected but localhost:8000 is not healthy. Check if backend is running locally.');
  }

  return {
    timestamp,
    environment,
    candidates,
    proxyTest,
    recommendations,
  };
}