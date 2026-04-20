#!/bin/bash
set -e

# ━━━ Export env vars so cron jobs can access them ━━━
# Cron runs in a clean shell — it doesn't inherit container env vars.
# Write them to a file that the crontab sources before each job.
printenv | grep -v "no_proxy" > /etc/environment

# ━━━ Install crontab ━━━
if [ -f /app/crontab ]; then
    crontab /app/crontab
    echo "[entrypoint] Crontab installed"
fi

# ━━━ Start cron daemon in background ━━━
cron
echo "[entrypoint] Cron daemon started"

# ━━━ Run migrations ━━━
echo "[entrypoint] Running alembic migrations..."
cd /app && alembic upgrade head

# ━━━ Start the main application (exec replaces shell — PID 1) ━━━
echo "[entrypoint] Starting uvicorn..."
exec "$@"
