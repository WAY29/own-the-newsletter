# Separate Admin Frontend and FastAPI Backend

The admin UI is a separate TypeScript frontend built with shadcn/ui, and FastAPI provides the backend API plus RSS feed endpoints. This rejects the simpler single-process model where FastAPI serves a bundled frontend, because the admin panel is expected to evolve as a real frontend application; the cost is running or deploying a separate frontend service and handling cross-origin or proxy configuration.
