I added a render.yaml manifest to define the frontend service for Render.

How this helps
- You can import this repo into Render and it will detect the render.yaml to create the service automatically.
- The manifest points at the add-supabase-integration branch and uses the Dockerfile in frontend/Dockerfile.
- Environment variables are declared but values are intentionally empty so you must set them in the Render dashboard (or via the Render API/CLI) to deploy.

Next steps to deploy on Render (GUI)
1. Go to https://dashboard.render.com and sign in.
2. Click New → Web Service.
3. Choose "Connect a repository" → select GitHub and authorize if needed.
4. Select the repository: santoshkumar-art/Surveillance_border.
5. Render should detect render.yaml and offer to create services described there. If not, choose to "Import repository" and pick the service defined in render.yaml.
6. After import, go to the service settings and add the environment variables:
   - VITE_SUPABASE_URL (value: https://<your-project-ref>.supabase.co)
   - VITE_SUPABASE_ANON_KEY (value: anon-...)
   Note: Mark the anon key as secret if desired (Render will store it encrypted).
7. Start the service (it will build the Docker image using frontend/Dockerfile and deploy).
8. Enable Auto-Deploy so pushes to add-supabase-integration automatically trigger redeploys.

If you want to use the Render CLI
- Install: brew install render-cli (or npm i -g @render/cli)
- Login: render login
- Create from manifest: render services create --file render.yaml
  (You may still need to set env vars in the dashboard or via `render services update`)

Important notes
- Do NOT put SUPABASE_SERVICE_ROLE_KEY or DATABASE_URL into frontend envs. Only the anon key is required by the client.
- After deploying, confirm /env.js is served and includes the VITE_* values (open <your-app>/env.js).

If you want, I can also:
- Open a PR that adds render.yaml to the default branch (I already added it to add-supabase-integration). Tell me to "open PR".
- Create a second service manifest for a backend (if you want a server to hold the service-role key and run migrations).
