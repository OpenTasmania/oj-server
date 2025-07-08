#!/bin/bash

# Create a self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout tls.key -out tls.crt -sha256 -days 365 -nodes -subj "/CN=localhost"

# Create a Kubernetes secret from the certificate
kubectl create secret tls self-signed-cert --cert=tls.crt --key=tls.key --dry-run=client -o yaml > secret.yaml
