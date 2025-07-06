# Use a Go builder image
FROM golang:1.19-alpine AS builder

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

# Expose the default pg_tileserv port
EXPOSE 7800

# The entrypoint will be configured in the Kubernetes manifest
ENTRYPOINT [ "pg_tileserv" ]
