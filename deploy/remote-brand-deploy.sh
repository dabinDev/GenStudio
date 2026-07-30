set -euo pipefail

release=/tmp/genstudio-brand-release
ts=$(date +%Y%m%d%H%M%S)
image_archive=${GENSTUDIO_IMAGE_ARCHIVE:-}
image_tag=${GENSTUDIO_IMAGE_TAG:-}

if [ -n "$image_archive" ] || [ -n "$image_tag" ]; then
  if [ -z "$image_archive" ] || [ -z "$image_tag" ]; then
    echo "GENSTUDIO_IMAGE_ARCHIVE and GENSTUDIO_IMAGE_TAG must be provided together." >&2
    exit 1
  fi
  if [ ! -f "$image_archive" ]; then
    echo "Prebuilt image archive not found: $image_archive" >&2
    exit 1
  fi
fi

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

commit_sha=""
if [ -f "$release/RELEASE_VERSION" ]; then
  commit_sha=$(sed -n 's/^GENSTUDIO_COMMIT_SHA=//p' "$release/RELEASE_VERSION" | head -n 1)
fi
if [ -z "$commit_sha" ] && [ -d "$release/.git" ]; then
  commit_sha=$(git -C "$release" rev-parse --short=12 HEAD 2>/dev/null || true)
fi
if [ -z "$commit_sha" ]; then
  commit_sha=$(date -u +release-%Y%m%d%H%M%S)
fi
build_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)
version=$(date -u +%Y.%m.%d.%H%M%S)

python3 - "$version" "$commit_sha" "$build_time" <<'PY'
from pathlib import Path
import sys

version, commit_sha, build_time = sys.argv[1:4]
p = Path('/opt/genstudio/deploy/.env')
lines = p.read_text().splitlines() if p.exists() else []
updates = {
    'GENSTUDIO_VERSION': version,
    'GENSTUDIO_COMMIT_SHA': commit_sha,
    'GENSTUDIO_BUILD_TIME': build_time,
}
seen = set()
next_lines = []
for line in lines:
    key = line.split('=', 1)[0] if '=' in line else ''
    if key in updates:
        next_lines.append(f'{key}={updates[key]}')
        seen.add(key)
    else:
        next_lines.append(line)
for key, value in updates.items():
    if key not in seen:
        next_lines.append(f'{key}={value}')
p.write_text('\n'.join(next_lines) + '\n')
PY

if [ -n "$image_archive" ]; then
  docker load --input "$image_archive"
  docker image inspect "$image_tag" >/dev/null
  if docker image inspect genstudio-api:latest >/dev/null 2>&1; then
    docker tag genstudio-api:latest "genstudio-api:backup-$ts"
  fi
  docker tag "$image_tag" genstudio-api:latest
  docker compose up -d --no-build genstudio-api
else
  docker compose build genstudio-api
  docker compose up -d genstudio-api
fi
sleep 5

if ! docker exec nginx sh -c 'paths=""; for d in /etc/nginx/conf.d /etc/nginx/sites-enabled; do [ -d "$d" ] && paths="$paths $d"; done; [ -n "$paths" ] && grep -R "location /admin/" $paths >/dev/null 2>&1'; then
  echo "Nginx is missing a /admin/ location. Install deploy/nginx.conf or add the documented /admin/ fallback before releasing." >&2
  exit 1
fi

docker exec nginx nginx -t
docker exec nginx nginx -s reload
curl -fsS http://127.0.0.1:18082/api/health
