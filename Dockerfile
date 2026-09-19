# Frontend build
FROM node:20-bookworm AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# The frontend uses same-origin /api routes in production.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# Runtime image
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BSS_DATA_DIR=/var/lib/bss/data \
    BSS_MODELS_DIR=/var/lib/bss/models \
    BSS_DATABASE_URL=sqlite:////var/lib/bss/data/border_security.db

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg nginx gettext-base libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip \
    && pip install --extra-index-url https://download.pytorch.org/whl/cpu -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker/start.sh /app/docker/start.sh
RUN chmod +x /app/docker/start.sh \
    && mkdir -p /var/lib/bss/data /var/lib/bss/models \
    && rm -f /etc/nginx/sites-enabled/default

EXPOSE 10000
CMD ["sh", "/app/docker/start.sh"]
