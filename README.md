# HireX Backend — Part 1

FastAPI + PostgreSQL + Firebase Auth

## Local Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 15
- Redis 7
- Firebase project with service account credentials

### Steps

1. Copy env file and fill in values:
   ```bash
   cp .env.example .env
   ```

2. Add your Firebase service account JSON as `firebase-credentials.json` in this directory.

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run database migrations:
   ```bash
   alembic upgrade head
   ```

5. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```

API docs available at: http://localhost:8000/docs

### Docker (recommended)
```bash
docker-compose up --build
```

### Run migrations in Docker
```bash
docker-compose exec api alembic upgrade head
```
