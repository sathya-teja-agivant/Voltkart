# VoltKart Backend (MVP)

## 1. Setup

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set your Neon `DATABASE_URL` and `GROQ_API_KEY`.

The database URL should use SQLAlchemy's psycopg driver format:
`postgresql+psycopg://...`

## 2. Seed the database

```bash
python -m seed
```

This creates the MVP tables and inserts synthetic laptop and policy records. For a growing project, replace `create_all` with Alembic migrations before changing schemas.

## 3. Run

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs.

## 4. Main endpoints

- `GET /health`
- `GET /db-check`
- `GET /api/v1/products`
- `GET /api/v1/products/{product_id}`
- `POST /api/v1/chat/message`
- `POST /api/v1/conversations`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}/messages`
- `DELETE /api/v1/conversations/{conversation_id}`

## MVP limitations

This is a local development MVP, not a production-ready commerce system. It intentionally omits authentication, admin CRUD, feedback, image uploads and deployment. Conversation ownership uses a fixed local demo user and must be replaced with authenticated user identity before multi-user use. Review and refine the recommendation filters and policy retrieval as the catalog grows.
