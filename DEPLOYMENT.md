# Deployment

This app is best deployed as a single Docker Compose service on a small VPS for the MVP stage. That matches the current architecture: one FastAPI app, one SQLite database file, local generated outputs, and one in-process worker.

## Target

- Ubuntu 24.04 VPS with 2-4 GB RAM
- Docker and Docker Compose plugin
- A domain pointed to the VPS
- A reverse proxy such as Caddy or Nginx for HTTPS

## Server Setup

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Log out and back in so Docker group membership applies.

## App Setup

```bash
git clone <your-repo-url> lecture-notes
cd lecture-notes
cp .env.example .env
```

Edit `.env`:

```text
APP_ENV=production
APP_SECRET_KEY=<generate-a-long-random-value>
PUBLIC_BASE_URL=https://notes.example.com
ALLOW_DEV_PASSWORD_RESET=false
MAX_UPLOAD_MB=500
OLLAMA_URL=http://host.docker.internal:11434/api/generate
OLLAMA_MODEL=llama3.2:1b
```

Create persistent directories and migrate:

```bash
mkdir -p data outputs
docker compose run --rm app python migrate_legacy.py
docker compose up -d --build
```

Check health:

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

## HTTPS

Put a reverse proxy in front of `127.0.0.1:8000` and terminate TLS there. Keep `APP_ENV=production` so secure cookies and HSTS are enabled. Example Caddyfile:

```text
notes.example.com {
  reverse_proxy 127.0.0.1:8000
}
```

## Backups

Back up these paths before every deploy:

```text
data/notes.db
outputs/
```

The migration command creates a timestamped SQLite backup by default. For a startup-scale hosted product, move the database to PostgreSQL and generated files to S3-compatible object storage; the current file paths are already centralized behind `file_store.py`.

## Deploys

```bash
git pull
docker compose build
docker compose run --rm app python migrate_legacy.py
docker compose up -d
docker compose logs -f --tail=100 app
```

## Monitoring

- `GET /healthz`: process health
- `GET /readyz`: database and output directory readiness
- `GET /metrics`: minimal queue depth and recent failures
- `SENTRY_DSN`: reserved hook for error tracking; off by default

Do not log transcript content. Existing logs use IDs and events only.
