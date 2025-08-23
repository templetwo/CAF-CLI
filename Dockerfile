# Stage 1: Build the agent
FROM node:20-slim AS builder
WORKDIR /usr/src/app

# Copy project files
COPY package*.json ./
COPY tsconfig.json ./
COPY .env ./
COPY src ./src

# Install dependencies and build the TypeScript code
RUN npm install
RUN npm run build

# Stage 2: Production environment
FROM node:20-slim
WORKDIR /usr/src/app

# Copy only the necessary files from the builder stage
COPY --from=builder /usr/src/app/node_modules ./node_modules
COPY --from=builder /usr/src/app/dist ./dist
COPY --from=builder /usr/src/app/.env ./.env

# The command to run the agent
ENTRYPOINT ["node", "dist/agent/index.js", "run"]
