# Use a Go builder image
FROM golang:1.22-alpine AS builder

# Install git and build dependencies
RUN apk add --no-cache git build-base

# Clone and build pg_tileserv
RUN git clone https://github.com/CrunchyData/pg_tileserv.git /go/src/github.com/CrunchyData/pg_tileserv
WORKDIR /go/src/github.com/CrunchyData/pg_tileserv/
RUN go build -o /pg_tileserv .

# Use a minimal alpine image for the final container
FROM alpine:latest

# Copy the built binary from the builder stage
COPY --from=builder /pg_tileserv /usr/local/bin/

# Create a non-root user and group
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Create a directory for the application data
RUN mkdir -p /var/lib/pg_tileserv && chown -R appuser:appgroup /var/lib/pg_tileserv

# Switch to non-root user
USER appuser

# Expose the default pg_tileserv port
EXPOSE 7800

# The entrypoint will be configured in the Kubernetes manifest
ENTRYPOINT [ "pg_tileserv" ]
