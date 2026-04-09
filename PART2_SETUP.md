# HireX Part 2 — Setup Instructions

## 1. Run migrations
```bash
cd hirex_backend
alembic upgrade head
```

## 2. Seed tasks
```bash
python -m seeds.tasks_seed
```

## 3. Start the server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **Important for physical device testing:** Use `--host 0.0.0.0` so the server accepts connections from your phone on the local network. Then set `API_BASE_URL=http://<your-machine-ip>:8000` in `hirex_app/.env`.

## 4. Flutter — install packages
```bash
cd hirex_app
flutter pub get
```

## 5. Run the app
```bash
flutter run
```
