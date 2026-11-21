FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY certs /etc/nginx/certs
EXPOSE 8080 8443
CMD ["nginx", "-g", "daemon off;"]
