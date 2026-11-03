FROM node:22-alpine AS builder
WORKDIR /app
COPY apps/web/package*.json ./
RUN npm install --no-audit --no-fund
COPY apps/web/ ./
RUN npm run build
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
