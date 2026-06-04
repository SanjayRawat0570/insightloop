# InsightLoop (Scaffold)

This repo contains a scaffold for InsightLoop — an AI-native BI platform.

Folders:
- backend/ — FastAPI backend, agents, tasks, utils
- frontend/ — Next.js frontend (App Router)

See `backend/requirements.txt` and `frontend/package.json` for dependencies.

Quick start (dev):

1. Create a Python virtualenv and install backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

2. Start backend:

```powershell
uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000
```

3. Start frontend:

```bash
cd frontend
pnpm install
pnpm dev
```

Docker compose is provided for a full-stack dev environment.
