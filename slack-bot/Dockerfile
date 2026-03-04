FROM node:18-alpine AS node-base

WORKDIR /app

# Copy package files
COPY slack-bot/package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY slack-bot/src/ ./src/

# Build stage for kagent CLI
FROM --platform=$BUILDPLATFORM golang:1.24.1-alpine AS cli-builder

ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETOS
ARG TARGETARCH

WORKDIR /workspace

# Copy the Go source
COPY go/go.mod go/go.sum ./
RUN go mod download

COPY go/cli ./cli
COPY go/autogen ./autogen

# Build kagent CLI
RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} go build -a -o kagent ./cli/cmd/kagent

# Final stage
FROM node:18-alpine

WORKDIR /app

# Copy Node.js app from node-base stage
COPY --from=node-base /app ./

# Copy kagent CLI binary
COPY --from=cli-builder /workspace/kagent /usr/local/bin/kagent

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S slackbot -u 1001

USER slackbot

EXPOSE 3000

CMD ["node", "src/index.js"] 