# DataPath FastAPI

This API provides PostgreSQL-backed registration/login and a **server-streamed sample reply**. It does not call RAG or the LLM yet.

Use Python 3.13 or newer as required by the project. From the project root:

1. Install the Python dependencies with `uv sync`.
2. Copy `.env.example` to `.env`. Generate a unique secret with `python -c "import secrets; print(secrets.token_hex(32))"` and put it in `SESSION_SECRET` in `.env`. The example PostgreSQL credentials match `docker-compose.yaml`; change them together if needed.
3. Start PostgreSQL with `docker compose up -d postgres` (or use an existing local PostgreSQL server).
4. Apply the schema with `uv run alembic upgrade head`.
5. Start the API with `uv run uvicorn api.main:app --reload`.
6. Start the frontend following [frontend/README.md](../frontend/README.md) and open `http://localhost:5500/?api=http://localhost:8000`.

No online SQL account is required. The cookie is HTTP-only and SameSite Strict. For HTTPS deployment, set `COOKIE_SECURE=true`, use a strong `SESSION_SECRET`, and set `FRONTEND_ORIGIN` to the exact frontend origin.

Routes: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`, and `POST /chat/stream`. The stream sends `text` events followed by `done`; it is intentionally labeled as a simulated answer.
