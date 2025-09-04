# Multi-stage build for optimized production image
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files for dependency caching
COPY package.json package-lock.json ./

# Install all dependencies with npm ci for reproducible builds
RUN npm ci --no-audit --no-fund && npm cache clean --force

# Copy source code
COPY . .

# Build the application (client and server)
RUN npm run build && \
    npx esbuild server/index.ts --platform=node --packages=external --bundle --format=esm --outfile=dist/server.js && \
    mkdir -p dist/logs/logins dist/logs/statements

# Production stage
FROM node:20-alpine AS production

WORKDIR /app

# Install system dependencies for security and process management
RUN apk add --no-cache dumb-init tini curl && \
    addgroup -g 1001 -S nodejs && \
    adduser -S wealthcommander -u 1001 -G nodejs

# Copy package files and install only production dependencies
COPY package.json package-lock.json ./
RUN npm ci --only=production --no-audit --no-fund && \
    npm cache clean --force && \
    rm -rf ~/.npm

# Copy built application and data from builder stage
COPY --from=builder --chown=wealthcommander:nodejs /app/dist ./dist
COPY --from=builder --chown=wealthcommander:nodejs /app/data ./data
COPY --from=builder --chown=wealthcommander:nodejs /app/shared ./shared

# Create persistent directories with proper ownership
RUN mkdir -p /app/logs/logins /app/logs/statements && \
    chown -R wealthcommander:nodejs /app/logs /app/data

# Set production environment variables
ENV NODE_ENV=production \
    PORT=8080 \
    NODE_OPTIONS="--max-old-space-size=512"

# Switch to non-root user for security
USER wealthcommander

# Expose port
EXPOSE 8080

# Improved health check with proper error handling
HEALTHCHECK --interval=30s --timeout=15s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8080/api/status || exit 1

# Use tini as init system for proper signal handling
ENTRYPOINT ["tini", "--"]
CMD ["node", "dist/server.js"]