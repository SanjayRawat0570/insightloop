# InsightLoop (Scaffold)

This repo contains a scaffold for InsightLoop — an AI-native BI platform.

Folders:
- backend/ — FastAPI backend, agents, tasks, utils
- frontend/ — Next.js frontend (App Router)

See `backend/requirements.txt` and `frontend/package.json` for dependencies.

Quick start (dev, no Docker):

1. Backend setup (from `backend/`):

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Start backend (from `backend/`):

```powershell
.\start.ps1
```

3. Frontend setup and start (from `frontend/`):

```powershell
cd frontend
npm install
.\start.ps1
```

4. Verify:

```powershell
curl http://localhost:8000/health
curl http://localhost:3000
```

Notes:
- `backend/.env` is read by `backend/start.ps1` if present.
- If MongoDB is unavailable during startup, the API logs a warning and still boots for local development.
