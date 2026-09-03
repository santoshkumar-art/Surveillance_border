#!/bin/sh
set -e

# Create env.js at runtime so the client can read runtime env vars
cat > /usr/share/nginx/html/env.js <<'EOT'
window.__env = {
  VITE_SUPABASE_URL: "${VITE_SUPABASE_URL}",
  VITE_SUPABASE_ANON_KEY: "${VITE_SUPABASE_ANON_KEY}"
};
EOT

# If any var is undefined, env.js will contain "undefined" strings — avoid leaking secrets.

# Start nginx
exec nginx -g 'daemon off;'
