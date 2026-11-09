FROM node:22-alpine AS builder
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
ARG NGINX_CONFIG=deploy/nginx.conf
COPY ${NGINX_CONFIG} /etc/nginx/conf.d/default.conf
EXPOSE 80
