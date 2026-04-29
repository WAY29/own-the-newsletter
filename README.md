# Own New Newsletter

Own New Newsletter is a personal self-hosted service that reads newsletters from an existing IMAP mailbox and publishes matching messages as private RSS feeds.

The first version includes:

- FastAPI backend with admin-token login, HttpOnly sessions, feed CRUD, IMAP validation/preview/sync, SQLite state, encrypted IMAP passwords, RSS publishing, and random feed URLs.
- React + Vite admin panel for managing feed rules and triggering syncs.
- Docker Compose deployment with Nginx same-origin routing for `/admin`, `/api`, and `/f/{random}.xml`.

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080/admin/` and log in with `OTN_ADMIN_TOKEN`.

## Local Development

Backend:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Backend tests:

```bash
cd backend
uv run pytest
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Runtime Configuration

See `.env.example` for required and optional environment variables. `OTN_SECRET_KEY` must remain stable because it is used to decrypt stored IMAP passwords.

The durable backup set is:

- SQLite database at `OTN_DATABASE_PATH`
- Feed files at `OTN_FEEDS_DIR`
- `.env` or equivalent runtime secrets
