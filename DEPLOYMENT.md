# Deployment with Docker and Render

This repository is configured as a single Render web service. The Docker image:

- builds the Vite/React frontend;
- runs the FastAPI backend and serves the frontend through nginx;
- proxies `/api/*` and WebSocket traffic to FastAPI;
- installs ffmpeg and the CPU computer-vision dependencies;
- stores the SQLite database, uploaded videos, renders, snapshots, and downloaded model weights under `/var/lib/bss`.

## Deploy on Render

1. Push this repository to GitHub.
2. In Render, choose **New → Blueprint** and select this repository.
3. Render will detect `render.yaml` and create `surveillance-border`.
4. Review the generated `BSS_ADMIN_PASSWORD` and deploy.
5. Open the generated `onrender.com` URL and sign in with:
   - username: `officer` (or the value configured in `BSS_ADMIN_USERNAME`)
   - password: the generated `BSS_ADMIN_PASSWORD`

The service health endpoint is `/api/health`. The Render blueprint uses a persistent 10 GB disk because model weights and uploaded footage must survive deploys. The `starter` plan is intentional because persistent disks are not available on Render's free web services.

## Important production settings

- Replace the generated bootstrap password after the first login if the application supports changing it, and keep the Render secret values private.
- Increase the disk size if storing substantial footage; each uploaded and annotated video consumes disk space.
- Set `BSS_ENABLE_PLATE_OCR=true` only when OCR is needed; it downloads additional model weights and uses more CPU/RAM.
- Render's default request timeout and available CPU may make long video analysis slow. For production workloads, use a larger instance and consider PostgreSQL/task-queue scaling as described in the main README.
- If you use a custom domain, same-origin frontend/API requests continue to work without changing `VITE_API_BASE_URL`.

## Local Docker run

```bash
docker build -t surveillance-border .
docker run --rm -p 10000:10000 \
  -e BSS_SECRET_KEY=replace-with-a-long-random-secret \
  -e BSS_ADMIN_PASSWORD=replace-with-a-strong-password \
  -e BSS_CORS_ORIGINS=http://localhost:10000 \
  -v surveillance-border-data:/var/lib/bss \
  surveillance-border
```

Then open <http://localhost:10000>.
