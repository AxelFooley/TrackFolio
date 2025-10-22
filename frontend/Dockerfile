# Frontend Dockerfile for Portfolio Tracker - Multi-stage build with runtime environment support
# Stage 1: Builder
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json ./

# Clear npm cache and install dependencies with npm ci for reproducible builds
RUN npm cache clean --force && \
    npm ci

# Copy application code - maintain src structure for Next.js App Router
COPY . .

# Build Next.js application with standalone output
# Note: BACKEND_API_URL is a RUNTIME variable, not needed at build time
RUN npm run build

# Stage 2: Production
FROM node:18-alpine AS runner

WORKDIR /app

# Set NODE_ENV to production
ENV NODE_ENV=production

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Install curl for health checks
RUN apk add --no-cache curl

# Copy package files
COPY package.json package-lock.json ./

# Clear npm cache and install production dependencies only
RUN npm cache clean --force && \
    npm ci --only=production && \
    npm cache clean --force

# Copy built application from builder stage
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# Set correct permissions
RUN chown -R nextjs:nodejs /app

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Set environment variables
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"
# Runtime backend API URL - this can be set at runtime via docker-compose or environment
# BACKEND_API_URL is not set here to allow runtime configuration
# NEXT_PUBLIC_API_URL is used for client-side API calls (fallback)

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1

# Run in production mode
CMD ["node", "server.js"]
