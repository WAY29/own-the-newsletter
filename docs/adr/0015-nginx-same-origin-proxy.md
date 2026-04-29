# Nginx Same-Origin Proxy

Docker Compose production deployment uses Nginx as the same-origin reverse proxy for the React admin frontend and FastAPI backend. This favors explicit, familiar proxy configuration over Caddy's automatic TLS behavior, while keeping the public URL space stable across `/admin`, `/api`, and `/f/{random}.xml`.
