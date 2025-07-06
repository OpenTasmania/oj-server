# Use the official Apache httpd image
FROM httpd:2.4

# Copy a custom configuration file.
# In Kubernetes, this would likely be mounted from a ConfigMap.
COPY httpd.conf /usr/local/apache2/conf/httpd.conf

EXPOSE 80
