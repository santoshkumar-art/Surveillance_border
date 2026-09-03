# Supabase integration for Surveillance_border

This document explains how the repository has been wired to Supabase and how to configure it locally and in CI.

## Files added on branch `add-supabase-integration`

- frontend/src/lib/supabaseClient.ts — Supabase client (Vite-compatible)
- frontend/src/lib/auth.ts — small auth helpers (signUp, signIn, signOut)
- frontend/src/lib/db.ts — simple DB helpers for devices and alerts
- db/init.sql — SQL schema + RLS policies
- .env.example — example env vars

## Quick local setup

1. Create a Supabase project at https://app.supabase.com and copy the Project URL and anon key.
2. Create a file `frontend/.env.local` with:

VITE_SUPABASE_URL=https://<your-project-ref>.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key>

3. Install dependencies and run dev server from the repo root:

npm install
cd frontend
npm install
npm run dev

4. To create tables and policies, run the SQL in `db/init.sql` using the Supabase SQL editor or the Supabase CLI:

# using supabase CLI
npx supabase sql "$(cat db/init.sql)"

Or copy-paste the `db/init.sql` contents into the SQL editor at app.supabase.com.

## CI and secrets

- Add the following repository secrets in GitHub (Settings → Secrets):
  - SUPABASE_URL
  - SUPABASE_SERVICE_ROLE_KEY (server/CI only)
  - DATABASE_URL (optional)

If you enable migrations in CI, make sure to set these secrets and do NOT print them in logs.

## Notes

- The anon key is safe to use on the client. Never commit the service role key.
- The SQL sets up RLS and example policies. Adjust policies to match your app's auth model.
