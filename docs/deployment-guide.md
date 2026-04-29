# Deployment Guide

Generic deployment instructions. The bot has no OS-specific runtime requirements — adapt the package manager / supervisor commands to your environment.

## Requirements

- Python 3.11 or newer
- A process supervisor (systemd, Docker, supervisord, pm2, etc.)
- Outbound HTTPS to Discord and PUBG APIs
- ~256 MB RAM is enough for a private server with <10 members; add 2 GB swap if your VPS has <2 GB RAM

## Install

1. Clone the repo to your chosen app directory (e.g. `/opt/discord-bot`, `~/apps/ae-metrics`).
2. Create a virtualenv and install dependencies:
   ```bash
   python3.11 -m venv .venv
   .venv/bin/pip install --upgrade pip
   .venv/bin/pip install -r requirements.txt
   ```
3. Create `.env` from `.env.example` and fill in secrets.
4. Run once in foreground to confirm slash commands sync:
   ```bash
   .venv/bin/python -m bot.main
   ```
5. Stop with Ctrl+C, then hand off to your supervisor.

## systemd (example)

A template lives at [`docs/discord-bot.service.template`](discord-bot.service.template). Replace the `__PLACEHOLDERS__`, copy to `/etc/systemd/system/discord-bot.service`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now discord-bot
sudo journalctl -u discord-bot -f
```

## Docker (example)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot ./bot
CMD ["python", "-m", "bot.main"]
```

Mount `.env` and a volume for `bot.db`:

```bash
docker run -d --name ae-metrics \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -e DB_PATH=/app/data/bot.db \
  --restart unless-stopped \
  ae-metrics
```

## Updates

```bash
git pull --ff-only
.venv/bin/pip install -r requirements.txt
sudo systemctl restart discord-bot   # or: docker restart ae-metrics
```

## Config rotation

If you rotate Discord or PUBG secrets:

1. Edit the relevant key in `.env` on the host.
2. Restart the service so the bot reloads settings.

## Logs

The bot logs to stdout/stderr only. Capture via your supervisor:
- systemd: `journalctl -u discord-bot -f`
- Docker: `docker logs -f ae-metrics`
- For on-disk rotation, redirect stdout in your unit (`StandardOutput=append:/var/log/...`) and configure `logrotate`.
