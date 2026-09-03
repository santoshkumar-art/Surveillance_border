# Stage 1 - build the Vite app
FROM node:18-alpine AS build

WORKDIR /app

# install dependencies
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install

# copy source and build
COPY frontend/ .
RUN npm run build

# Stage 2 - serve with nginx
FROM nginx:stable-alpine

COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx config
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Entrypoint script generates env.js at container start from runtime env vars
COPY frontend/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Ensure env.js is loaded by index.html (insert script tag if not present)
RUN if ! grep -q "env.js" /usr/share/nginx/html/index.html; then \
      sed -i '/<\/head>/i <script src="/env.js"></script>' /usr/share/nginx/html/index.html; \
    fi

EXPOSE 80
ENTRYPOINT ["/docker-entrypoint.sh"]
