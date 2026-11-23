FROM nginxinc/nginx-unprivileged:1.27-alpine

USER root
# Grant CAP_NET_BIND_SERVICE so the unprivileged nginx user (101) can bind standard ports 80 and 443
RUN apk add --no-cache libcap \
    && setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx \
    && mkdir -p /etc/nginx/certs/active /var/www/certbot \
    && chown -R 101:101 /etc/nginx/certs /var/www/certbot /var/log/nginx /tmp

COPY --chmod=755 docker-entrypoint.sh /docker-entrypoint.sh
COPY nginx.conf /etc/nginx/nginx.conf
COPY certs /etc/nginx/certs

USER 101
EXPOSE 80 443 8080 8443
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
