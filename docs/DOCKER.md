# Containerization instructions for Surveillance_border (frontend)

This project includes a Dockerfile to build the Vite + React frontend and serve it with nginx, plus a docker-compose.yml to run it locally.

Key points
- The frontend reads runtime configuration from `env.js` generated when the container starts. This file is populated from the environment variables VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.
- Do NOT commit real secrets to the repository. Use a local `.env` file for docker-compose or pass env vars during run.

Build and run with Docker

1) Build the image (optional: pass build args)

# from repository root
docker build -t surveillance-frontend -f frontend/Dockerfile .

2) Run the container with runtime env vars

# runtime envs must be provided so env.js contains correct values
docker run -p 8080:80 \
  -e VITE_SUPABASE_URL="https://your-project-ref.supabase.co" \
  -e VITE_SUPABASE_ANON_KEY="anon-..." \
  surveillance-frontend

OR using docker-compose (recommended for local development)

# create a local .env file (DO NOT commit)
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_ANON_KEY=anon-...

# then
docker-compose up --build

Notes about build-time vs runtime env
- Vite normally embeds VITE_ env vars at build time. To support runtime configuration (so you don't rebuild the image for different environments), the container generates a small `env.js` file at startup that the app can read.
- The Dockerfile also inserts a <script src="/env.js"></script> tag into the built index.html so the generated env loader runs before your app code.

Supabase and secrets
- The service role key and database password are server-side secrets. Never expose them to frontend containers. Store them in your backend or CI as secrets.

Running a local Supabase instance
- If you need a local Supabase for development, install the supabase CLI and run `npx supabase start` separately. Running Supabase inside docker-compose is possible but recommended only if you need a full local stack.

Troubleshooting
- If your app shows blank page, open browser devtools and ensure `env.js` is loaded and window.__env has your VITE_* values.
- Check container logs: `docker logs <container>` or `docker-compose logs -f`.
