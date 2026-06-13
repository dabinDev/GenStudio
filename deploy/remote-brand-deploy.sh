set -euo pipefail

release=/tmp/genstudio-brand-release
ts=$(date +%Y%m%d%H%M%S)

rm -rf "$release"
mkdir -p "$release"
tar -xzf /tmp/genstudio-brand-release.tar.gz -C "$release"

cd /opt/genstudio
mkdir -p /opt/genstudio_backups
if [ -d server ]; then cp -a server "/opt/genstudio_backups/server-$ts"; fi
if [ -d /opt/nginx/html/genstudio ]; then cp -a /opt/nginx/html/genstudio "/opt/genstudio_backups/fronted-$ts"; fi
if [ -d /opt/nginx/html/genstudio-admin ]; then cp -a /opt/nginx/html/genstudio-admin "/opt/genstudio_backups/admin-$ts"; fi

rsync -a --delete "$release/server/" /opt/genstudio/server/
rsync -a --delete "$release/docs/" /opt/genstudio/docs/
cp -f "$release/.dockerignore" /opt/genstudio/.dockerignore

mkdir -p /opt/nginx/html/genstudio
mkdir -p /opt/nginx/html/genstudio-admin
rsync -a --delete "$release/fronted/dist/" /opt/nginx/html/genstudio/
rsync -a --delete "$release/admin/dist/" /opt/nginx/html/genstudio-admin/

if ! grep -q '^GENSTUDIO_ADMIN_IDENTIFIERS=' /opt/genstudio/deploy/.env; then
  printf '\nGENSTUDIO_ADMIN_IDENTIFIERS=cylonai\n' >> /opt/genstudio/deploy/.env
else
  python3 - <<'PY'
from pathlib import Path

p = Path('/opt/genstudio/deploy/.env')
lines = p.read_text().splitlines()
updated = []
seen = False
for line in lines:
    if line.startswith('GENSTUDIO_ADMIN_IDENTIFIERS='):
        current = [item.strip() for item in line.split('=', 1)[1].split(',') if item.strip()]
        lower = {item.lower() for item in current}
        if 'cylonai' not in lower:
            current.append('cylonai')
        updated.append('GENSTUDIO_ADMIN_IDENTIFIERS=' + ','.join(current))
        seen = True
    else:
        updated.append(line)
if not seen:
    updated.append('GENSTUDIO_ADMIN_IDENTIFIERS=cylonai')
p.write_text('\n'.join(updated) + '\n')
PY
fi

docker compose build genstudio-api
docker compose up -d genstudio-api
sleep 5

if ! docker exec nginx sh -c 'paths=""; for d in /etc/nginx/conf.d /etc/nginx/sites-enabled; do [ -d "$d" ] && paths="$paths $d"; done; [ -n "$paths" ] && grep -R "location /admin/" $paths >/dev/null 2>&1'; then
  echo "Nginx is missing a /admin/ location. Install deploy/nginx.conf or add the documented /admin/ fallback before releasing." >&2
  exit 1
fi

docker exec nginx nginx -t
docker exec nginx nginx -s reload
curl -fsS http://127.0.0.1:18082/api/health
