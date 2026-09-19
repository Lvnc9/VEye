# VEye

VEye is an ISO-style **controlled-document management system** with a Persian (RTL) interface. Staff register a document slot (for example `PR-01-01`), compose its body from ordered content blocks, and route it through review, approval and sign-off. Jalali dates are used throughout.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Django 5, Django REST Framework, SimpleJWT (cookie auth) |
| Data | PostgreSQL 16, Redis 7 |
| Background jobs | Celery |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| Infrastructure | Docker Compose |

## Features

- National-code login with roll and level based permissions
- Personnel registration and account management
- Document registry: create, revise and search documents with automatic numbering
- Document designer: ordered content blocks, file attachments, logo and revision copies
- Dashboard with live counts, cached in Redis
- Persian RTL UI with Jalali dates

## Status

| Area | Status |
|---|---|
| Identity and permissions | Done |
| Document registry | Done |
| Document designer | Done |
| PDF generation with QR code (Celery) | In progress |
| Sign-off workflow and public verification page | Planned |
| History, bulk print, data import | Planned |

## Project structure

```
backend/     Django project (config/, apps/accounts, core, dashboard, documents)
frontend/    Next.js app (app/, components/, lib/)
docker-compose.yml
.env.example
```

## Getting started

Requires Docker and Docker Compose.

```bash
cp .env.example .env
# edit .env: set POSTGRES_PASSWORD and generate a DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/api/v1 |

Migrations run automatically when the backend container starts.

### Tests

```bash
docker compose exec backend python manage.py test
cd frontend && npm test
```

### Running without Docker

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.local.example` to `frontend/.env.local`. Then start PostgreSQL and Redis locally, and run `python manage.py runserver` in `backend/` and `npm run dev` in `frontend/`.

## Configuration

All configuration comes from environment variables. See [`.env.example`](.env.example). Never commit your real `.env`.
