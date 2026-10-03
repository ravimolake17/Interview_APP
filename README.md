# Agentic HR Recruitment System

Unified platform for resume screening, scheduling, blueprint planning, live AI interview, proctoring (Agent 5), and evaluation — one backend and one frontend install.

## Architecture

```
Resume + JD
    ↓
Agent 1: screening → shortlist
    ↓
Agent 2: save candidate → email → scheduling link
    ↓
Candidate schedules → hashed join link
    ↓
Agent 5 identity / proctoring + Agent 4 live AI interview room
    ↓
Agent 6 evaluation
```

## Project Structure

```
Interview_Agentic_AI/
├── backend/
│   ├── main.py                         # Unified FastAPI app
│   ├── agents/
│   │   ├── screening_agent/            # Agent 1
│   │   ├── scheduler_agent/            # Agent 2
│   │   ├── blueprint_agent/            # Agent 3
│   │   ├── interview_agent/            # Agent 4
│   │   ├── proctoring_agent/           # Agent 5 (fraud / proctoring)
│   │   └── evaluation_agent/           # Agent 6
│   ├── api/routes/
│   ├── requirements.txt                # All agents (including Agent 5)
│   └── alembic/
├── frontend/
│   ├── src/                            # HR + scheduling SPA
│   ├── agent5/                         # Proctoring UI (built via npm run build)
│   └── screening/                      # Agent 1 static UI
└── docker-compose.yml
```

## Quick Start

### 1. PostgreSQL

```powershell
docker compose up -d
```

Create database `interview_scheduler` if needed, then set `DATABASE_URL` / `CHECKPOINT_DB_URL` in `backend/.env`.

### 2. Backend (all agents)

```powershell
cd backend
py -3.11 -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Set AGENT5_SECRET_KEY to a unique string of at least 32 characters
alembic upgrade head
uvicorn main:app --reload --host 127.0.0.1 --port 8030
```

Agent 5 tables are created automatically in PostgreSQL schema `agent5` on first successful backend start.

### 3. Frontend (HR UI + proctoring UI)

```powershell
cd frontend
npm install
npm run build          # builds HR SPA + Agent 5 proctoring UI
npm run dev            # HR app at http://localhost:5173
```

- HR / scheduling: http://localhost:5173  
- Proctoring room (after build): http://127.0.0.1:8030/proctoring/  
- Agent 1 screening UI: http://127.0.0.1:8030/screening/

You do **not** need a separate Agent 5 Python install or a separate `cd frontend/agent5` build for normal use — `npm run build` from `frontend/` covers it.

## Auth model

| Who | Access |
|-----|--------|
| HR / Admin | Main app login (`public.users`) |
| Candidate | Hashed join link only — no Agent 5 password |

`AGENT5_SECRET_KEY` signs session tokens; it is not a login password.

## End-to-End Test

1. Open HR app → run screening / shortlist a candidate  
2. Schedule interview → open the join link  
3. Candidate completes verification → AI interview room  

## API docs

Interactive docs while the backend is running: http://127.0.0.1:8030/docs

## Production (two Azure VMs)

Step-by-step install, Postgres-on-app-VM-only, ports, Application Gateway, and systemd/NSSM commands:

[docs/AZURE_TWO_VM_DEPLOYMENT.md](docs/AZURE_TWO_VM_DEPLOYMENT.md)

