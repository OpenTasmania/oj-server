# Use the official Nginx image
FROM nginx:stable-alpine

# Copy a custom configuration file.
# In Kubernetes, this would likely be mounted from a ConfigMap.
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
