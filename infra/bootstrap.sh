#!/bin/bash
set -euo pipefail
dnf install -y docker git openssl
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL https://github.com/docker/compose/releases/download/v2.36.2/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
git clone '${repository}' /opt/fieldsense
cd /opt/fieldsense
umask 077
password=$(openssl rand -hex 24)
token=$(openssl rand -hex 32)
printf 'POSTGRES_PASSWORD=%s\nDATABASE_URL=postgresql+psycopg://fieldsense:%s@postgres:5432/fieldsense\nWRITE_TOKEN=%s\nDOMAIN=%s\nSEED_DATA=true\n' "$password" "$password" "$token" '${domain}' > .env
docker compose -f compose.yaml -f infra/compose.production.yaml up --build -d
