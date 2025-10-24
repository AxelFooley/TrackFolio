'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, CheckCircle, XCircle, RefreshCw } from 'lucide-react';
import {
  runBackendDiagnostics,
  BackendHealthStatus,
  findHealthyBackend
} from '@/lib/backend-health';

export default function ApiHealthPage() {
  const [loading, setLoading] = useState(false);
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const runDiagnostics = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await runBackendDiagnostics();
      setDiagnostics(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run diagnostics');
    } finally {
      setLoading(false);
    }
  };

  const testQuickHealth = async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await findHealthyBackend();
      setDiagnostics({
        timestamp: new Date().toISOString(),
        candidates: result ? [result] : [],
        proxyTest: { working: !!result },
        recommendations: result ? [] : ['No healthy backend found']
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Health check failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runDiagnostics();
  }, []);

  const getStatusIcon = (healthy: boolean) => {
    return healthy ?
      <CheckCircle className="h-5 w-5 text-green-500" /> :
      <XCircle className="h-5 w-5 text-red-500" />;
  };

  const getStatusBadge = (healthy: boolean) => {
    return healthy ?
      <Badge variant="default" className="bg-green-500">Healthy</Badge> :
      <Badge variant="destructive">Unhealthy</Badge>;
  };

  return (
    <div className="container mx-auto py-8 max-w-4xl">
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold">API Health Check</h1>
            <p className="text-muted-foreground">
              Test backend connectivity and API proxy functionality
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={testQuickHealth}
              disabled={loading}
              variant="outline"
              size="sm"
            >
              {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              Quick Test
            </Button>
            <Button
              onClick={runDiagnostics}
              disabled={loading}
              size="sm"
            >
              {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
              Run Diagnostics
            </Button>
          </div>
        </div>

        {error && (
          <Card className="border-red-200">
            <CardHeader>
              <CardTitle className="text-red-600">Error</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-red-600">{error}</p>
            </CardContent>
          </Card>
        )}

        {diagnostics && (
          <>
            {/* Environment Information */}
            <Card>
              <CardHeader>
                <CardTitle>Environment Information</CardTitle>
                <CardDescription>
                  Current runtime environment and configuration
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Node Environment:</span>
                    <Badge variant="outline" className="ml-2">
                      {diagnostics.environment.NODE_ENV}
                    </Badge>
                  </div>
                  <div>
                    <span className="font-medium">Docker Environment:</span>
                    <Badge variant={diagnostics.environment.isDockerEnvironment ? "default" : "outline"} className="ml-2">
                      {diagnostics.environment.isDockerEnvironment ? 'Yes' : 'No'}
                    </Badge>
                  </div>
                  <div>
                    <span className="font-medium">Docker Env Variable:</span>
                    <Badge variant="outline" className="ml-2">
                      {diagnostics.environment.DOCKER_ENV || 'Not set'}
                    </Badge>
                  </div>
                  <div>
                    <span className="font-medium">Backend API URL:</span>
                    <Badge variant="outline" className="ml-2">
                      {diagnostics.environment.BACKEND_API_URL || 'Not set'}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Backend Candidates */}
            <Card>
              <CardHeader>
                <CardTitle>Backend URL Candidates</CardTitle>
                <CardDescription>
                  Tested backend URLs and their health status
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {diagnostics.candidates.map((candidate: BackendHealthStatus, index: number) => (
                    <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(candidate.healthy)}
                        <div>
                          <p className="font-medium">{candidate.url}</p>
                          {candidate.responseTime && (
                            <p className="text-sm text-muted-foreground">
                              Response time: {candidate.responseTime}ms
                            </p>
                          )}
                          {candidate.error && (
                            <p className="text-sm text-red-600">{candidate.error}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {getStatusBadge(candidate.healthy)}
                        <p className="text-xs text-muted-foreground">
                          {new Date(candidate.timestamp).toLocaleTimeString()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* API Proxy Test */}
            <Card>
              <CardHeader>
                <CardTitle>API Proxy Test</CardTitle>
                <CardDescription>
                  Test the Next.js API route proxy functionality
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-3">
                  {getStatusIcon(diagnostics.proxyTest.working)}
                  <div>
                    <p className="font-medium">
                      {diagnostics.proxyTest.working ? 'Working' : 'Not Working'}
                    </p>
                    {diagnostics.proxyTest.backendUrl && (
                      <p className="text-sm text-muted-foreground">
                        Backend: {diagnostics.proxyTest.backendUrl}
                      </p>
                    )}
                    {diagnostics.proxyTest.error && (
                      <p className="text-sm text-red-600">{diagnostics.proxyTest.error}</p>
                    )}
                  </div>
                  <div className="ml-auto">
                    {getStatusBadge(diagnostics.proxyTest.working)}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Recommendations */}
            {diagnostics.recommendations.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Recommendations</CardTitle>
                  <CardDescription>
                    Suggestions based on diagnostic results
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {diagnostics.recommendations.map((recommendation: string, index: number) => (
                      <li key={index} className="flex items-start gap-2">
                        <div className="w-2 h-2 bg-blue-500 rounded-full mt-2 flex-shrink-0"></div>
                        <span className="text-sm">{recommendation}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            {/* Timestamp */}
            <div className="text-center text-sm text-muted-foreground">
              Last updated: {new Date(diagnostics.timestamp).toLocaleString()}
            </div>
          </>
        )}

        {!diagnostics && !loading && (
          <Card>
            <CardContent className="flex items-center justify-center py-8">
              <div className="text-center">
                <p className="text-muted-foreground mb-4">
                  No diagnostics data available
                </p>
                <Button onClick={runDiagnostics}>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Run Diagnostics
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}