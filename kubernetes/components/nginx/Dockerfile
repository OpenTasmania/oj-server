# Use the official Nginx image
FROM nginx:stable-alpine

# Copy a custom configuration file.
# In Kubernetes, this would likely be mounted from a ConfigMap.
COPY nginx.conf /etc/nginx/nginx.conf

# Set permissions for nginx directories
RUN chown -R nginx:nginx /var/cache/nginx \
    && chown -R nginx:nginx /var/log/nginx \
    && chown -R nginx:nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown -R nginx:nginx /var/run/nginx.pid

# Switch to non-root user
USER nginx

EXPOSE 80
