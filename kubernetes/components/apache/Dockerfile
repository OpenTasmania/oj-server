# Use the official Apache httpd image
FROM httpd:2.4

RUN apt-get update \
    && apt-get --yes upgrade \
    && apt-get --yes install libapache2-mod-tile \
    && apt-get clean \
    && apt-get --purge autoremove

COPY kubernetes/components/apache/httpd.conf /usr/local/apache2/conf/httpd.conf
COPY kubernetes/components/apache/mod_tile.conf /usr/local/apache2/conf/mod_tile.conf

EXPOSE 8080
