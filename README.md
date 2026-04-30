[中文版](README_CN.md)

# Own the Newsletter

A self-hosted tool that converts emails from your IMAP mailbox into private RSS feeds, with a clean web UI for management.

> The vast majority of this codebase was written by Codex and Claude.

## Inspiration

Inspired by [kill-the-newsletter.com](https://kill-the-newsletter.com/), which hosts its own mail server to receive newsletters. Instead of deploying a mail server, **Own the Newsletter** connects to your existing IMAP mailbox (Gmail, Outlook, Fastmail, etc.) to fetch newsletter emails.

This approach has a key advantage: you can use well-known email providers, avoiding subscription rejections caused by domain allowlists or blocklists that some newsletters enforce.

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/WAY29/own-the-newsletter.git
cd own-the-newsletter
cp .env.example .env
# Edit .env to set your own values (see Environment Variables below)
docker compose up --build
```

Open `http://localhost:8080/admin/` and log in with your `OTN_ADMIN_TOKEN`.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OTN_ADMIN_TOKEN` | `change-this-admin-token` | Token used to log in to the Admin Panel. **Change this before deployment.** |
| `OTN_SECRET_KEY` | `change-this-long-random-secret-key` | Encryption key for stored IMAP passwords. Must remain stable — changing it will invalidate all saved credentials. **Change this before deployment.** |
| `OTN_DATABASE_PATH` | `/data/own-newsletter.sqlite` | Path to the SQLite database file. |
| `OTN_FEEDS_DIR` | `/data/feeds` | Directory where generated RSS XML files are stored. |
| `OTN_BACKEND_PORT` | `8000` | Host port mapped to the FastAPI backend (direct access). |
| `OTN_FRONTEND_PORT` | `8080` | Host port mapped to the Nginx proxy serving the full application. |
| `OTN_PUBLIC_ORIGIN` | `http://localhost:8080` | The externally visible URL of the application. Update this if you change `OTN_FRONTEND_PORT` or deploy behind a reverse proxy. |
| `OTN_COOKIE_SECURE` | `false` | Set to `true` if serving over HTTPS to enable secure cookies. |
| `OTN_SESSION_DAYS` | `30` | Number of days an admin session remains valid. |
| `OTN_SCHEDULER_ENABLED` | `true` | Enable or disable the background IMAP sync scheduler. |
| `OTN_SCHEDULER_TICK_SECONDS` | `60` | Interval in seconds between scheduled sync checks. |
| `OTN_IMAP_TIMEOUT_SECONDS` | `30` | Timeout in seconds for IMAP connections. |
| `OTN_LOG_LEVEL` | `INFO` | Application log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |

## Local Development

**Backend:**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

**Backend tests:**

```bash
cd backend
uv run pytest
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'feat: add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

This project is licensed under the [MIT License](LICENSE).
