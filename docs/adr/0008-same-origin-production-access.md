# Same-Origin Production Access

The React admin frontend and FastAPI backend may run as separate internal services, but production exposes the admin panel, backend API, and RSS feed endpoints through one public origin. This keeps HttpOnly session cookies straightforward and avoids cross-origin credential handling for the admin panel while preserving independent frontend and backend development.
