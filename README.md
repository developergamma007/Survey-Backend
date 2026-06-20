# Survey Backend

FastAPI API for PulseSync / Survey-WebSite.

## Local development

```bash
python3 -m venv .venv
source venv/bin/activate   # or: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set DATABASE_URL
uvicorn main:app --reload --host 0.0.0.0 --port 8002
```

Health check: `http://127.0.0.1:8002/health`

## Audio uploads and HTTP 413

Survey audio is uploaded separately via `POST /api/surveys/upload-audio` (multipart), then referenced in `POST /surveys` as `audioKey`. This avoids oversized JSON bodies.

**nginx** defaults to `client_max_body_size 1m`, which causes **413 Payload Too Large** before FastAPI receives the audio. Add inside your API `server` or `location` block:

```nginx
client_max_body_size 25m;
client_body_timeout 120s;
proxy_read_timeout 120s;
proxy_send_timeout 120s;
```

Then validate and reload nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

`deploy/nginx-survey-backend.conf` has a ready-to-copy location block for the production proxy. Ensure S3 env vars are set in `.env` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`). The app also enforces `MAX_AUDIO_UPLOAD_BYTES` (default `26214400`, 25 MB), so keep nginx at or above that value.

## Production (PM2 + nginx on port 8000)

```bash
cd ~/Survey-Backend
git pull
source venv/bin/activate   # or: source .venv/bin/activate
pip install -r requirements.txt

# Must exist with DATABASE_URL (and optional S3_* keys)
test -f .env || { echo "Missing .env"; exit 1; }

pm2 delete survey-backend 2>/dev/null || true
pm2 start ecosystem.config.cjs
pm2 save

curl -s http://127.0.0.1:8000/health
```

If the process keeps restarting:

```bash
pm2 logs survey-backend --lines 80
```

Common fixes:

- Wrong module: use `main:app` (not `app:app`)
- Missing `.env` / `DATABASE_URL` in `~/Survey-Backend`
- PM2 `cwd` not set to `Survey-Backend` (use `ecosystem.config.cjs`)
