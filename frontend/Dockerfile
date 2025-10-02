# Build and run the Next.js frontend with Node 20.
FROM node:20-bullseye-slim

WORKDIR /app

# Enable pnpm (ships with Node via Corepack) and ensure it's on PATH.
RUN corepack enable pnpm

# Install dependencies based on the pnpm lockfile for reproducible builds.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

# Copy the remaining application code and build the production bundle.
COPY . ./
RUN pnpm run build

# Expose the port Next.js listens on and start the production server.
EXPOSE 3000
ENV NODE_ENV=production
CMD ["pnpm", "run", "start"]
