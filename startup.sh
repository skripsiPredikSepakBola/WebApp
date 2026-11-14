#!/bin/bash
set -e
cd /home/site/wwwroot

if [ -d ".git" ]; then
    git fetch --depth 1 origin main && git checkout -f FETCH_HEAD || true
fi

if [ ! -x "/tmp/antenv/bin/gunicorn" ]; then
    python -m venv /tmp/antenv
    /tmp/antenv/bin/pip install --upgrade pip
    /tmp/antenv/bin/pip install --no-cache-dir -r requirements.txt gunicorn
fi

(
    HOST="${WEBSITE_HOSTNAME:-skripsiwebapp-cehte7bwece0daad.indonesiacentral-01.azurewebsites.net}"
    while true; do
        sleep 540
        curl -fsS -m 15 -A "PitchPulseAI-KeepAlive/1.0" "https://${HOST}/api/health" >/dev/null 2>&1 || true
    done
) &

exec /tmp/antenv/bin/gunicorn --bind=0.0.0.0:${PORT:-8000} --timeout 180 --workers 1 app:app
