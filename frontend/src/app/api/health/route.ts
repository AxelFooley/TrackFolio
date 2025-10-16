import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  try {
    // Basic health check - if we can reach this endpoint, the app is running
    return NextResponse.json({
      status: 'healthy',
      app: 'Portfolio Tracker Frontend',
      environment: process.env.NODE_ENV || 'unknown',
      backendApiUrl: process.env.BACKEND_API_URL || 'not_set',
      publicApiUrl: process.env.NEXT_PUBLIC_API_URL || 'not_set',
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    return NextResponse.json(
      {
        status: 'unhealthy',
        error: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}