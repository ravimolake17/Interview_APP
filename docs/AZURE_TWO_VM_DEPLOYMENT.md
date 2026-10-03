# Interview Agentic AI — Azure two-VM deploy (your PRD)

This guide matches **Interview-PRD-RG** in **Central India**. Both VMs are **Ubuntu 24.04 LTS (ubuntu-pro)**. There is **no Blob** — Postgres, uploads, Chroma, and Agent 5 recordings stay on **local OS disks**. Postgres runs **only on Interview-app**.

**Do not split the Git repository.** Clone the same repo on both VMs. Same internal port **8030** on both machines.

Same VNet + **different subnet** + **different IP** is correct.

---

## Start here (VNet work is done)

Your manager already recreated **Interview-Proctor** on `vnet-centralindia-1`. Skip NIC swap / VM delete.

**Do this next, in order:**

1. **Start both VMs** if they are deallocated.
2. Confirm IPs in the inventory table below.
3. NSG + Postgres `pg_hba` for Proctor `172.17.0.4` (sections 2 and 5).
4. Give candidates a path to Agent 5: **public IP on Proctor** or later Application Gateway (Proctor still has **no public IP**).
5. Install packages, clone the repo, `.env`, systemd (section 4 onward).

---



## Your Azure inventory (2 Oct 2026)

Subscription: **RRKabel-Digital-Projects** (`bc4c282e-7d01-4f75-973d-30fc8eed157d`)  
Resource group: **Interview-PRD-RG**  
Region: **Central India**  
Backup vault: **Interview-PRD-backup**  
Only VNet in the RG: `vnet-centralindia-1`


|            | **Interview-app**                                         | **Interview-Proctor**                                        |
| ---------- | --------------------------------------------------------- | ------------------------------------------------------------ |
| Role       | HR, SuperAdmin, ATS, Agent 4, **local Postgres**          | Agent 5 only                                                 |
| Size       | Standard **D8alds v6** (8 vCPU, 16 GiB)                   | Standard **D4s v3** (4 vCPU, 16 GiB)                         |
| OS         | Ubuntu 24.04 LTS Pro                                      | Ubuntu 24.04 LTS Pro                                         |
| Public IP  | **20.244.34.0** (`Interview-app-ip`)                      | **None**                                                     |
| Private IP | **172.16.0.4**                                            | **172.17.0.4**                                               |
| VNet       | `vnet-centralindia-1`                                     | `vnet-centralindia-1` **(same)**                             |
| Subnet     | `snet-centralindia-1` (`172.16.0.0/24`)                   | `snet-centralindia-2`                                        |
| NIC        | `interview-app371`                                        | `interview-proctor858`                                       |
| NSG        | `Interview-app-nsg`                                       | `Interview-Proctor-nsg`                                      |
| OS disk    | `Interview-app_OsDisk_1_206404440af44819a4c58d75fb664452` | `Interview-Proctor_OsDisk_1_3845247815884ed91bddbe4498a2a91` |
| Process    | `uvicorn main:app`                                        | `uvicorn agents.proctoring_agent.main:app`                   |


No Application Gateway and no Blob in this resource group yet.

---



## Still open (needed for live candidate rooms)



### Proctor has no public IP

Pick **one**:

- **A (simplest now):** create a public IP, attach it to `interview-proctor858`. Join links use that IP.  
- **B (later):** Application Gateway on `vnet-centralindia-1`:
  - `app.yourcompany.com` → `172.16.0.4:8030`
  - `proctor.yourcompany.com` → `172.17.0.4:8030`

SSH to Proctor through App until it has a public IP:

```bash
ssh -J azureuser@20.244.34.0 azureuser@172.17.0.4
```



### Disk and shutdown

- Recordings stay on Proctor’s OS disk. Watch `df -h /`.
- Disable **9:00 PM IST auto-shutdown** if interviews run later.

---



## Where data lives (no Blob)


| Data               | VM                     | Path                                                    |
| ------------------ | ---------------------- | ------------------------------------------------------- |
| PostgreSQL         | **Interview-app only** | `/var/lib/postgresql/`                                  |
| Uploads, Chroma    | Interview-app          | repo `backend/`                                         |
| Agent 5 recordings | Interview-Proctor      | `/opt/apps/Interview_Agentic_AI/backend/storage/agent5` |
| Agent 5 models     | Interview-Proctor      | `/opt/apps/Interview_Agentic_AI/models/agent5`          |
| Azure Backup       | App first              | vault **Interview-PRD-backup**                          |


```bash
sudo mkdir -p /var/backups/interview
sudo -u postgres pg_dump -Fc interview_scheduler -f /var/backups/interview/interview_scheduler-$(date +%F).dump
```

---



## 0. Code readiness

Use a build with `AGENT5_EMBEDDED`, `INTERVIEW_API_PUBLIC_URL`, `/health/live`, and standalone `/proctoring/`.

**Same on both VMs:** git commit, `AGENT5_SECRET_KEY`, `npm run build`.

---



## 1. Traffic

```
HR / SuperAdmin ──► Interview-app  20.244.34.0 :8030
                         private 172.16.0.4
                         Postgres :5432
                              ▲
                              │  vnet-centralindia-1
                              │  snet-centralindia-1  ←→  snet-centralindia-2
                              │
Proctor Agent 5 ──────────────┘  172.17.0.4 :8030
                         recordings on local disk
```

- App: login, ATS, SuperAdmin, Agent 4
- Proctor: frames, audio, recording chunks, `/ws/sessions`
- Join email: `AGENT5_PUBLIC_URL` → Proctor `/proctoring/`

---



## 2. NSG (do this before Proctor can use Postgres)

Same VNet does **not** bypass NSG. App must allow **5432 from 172.17.0.4**.

### `Interview-app-nsg`


| Priority | Name                 | Source                         | Port | Action |
| -------- | -------------------- | ------------------------------ | ---- | ------ |
| 100      | SSH                  | your office / VPN IP           | 22   | Allow  |
| 110      | AppHttp              | Internet **or** Gateway subnet | 8030 | Allow  |
| 120      | PostgresFromProctor  | **172.17.0.4/32**              | 5432 | Allow  |
| 4096     | DenyPostgresInternet | Internet                       | 5432 | Deny   |


Do **not** allow 5432 from `0.0.0.0/0`. You can use source subnet `snet-centralindia-2` instead of a single IP.

### `Interview-Proctor-nsg`


| Priority | Name        | Source                                           | Port | Action |
| -------- | ----------- | ------------------------------------------------ | ---- | ------ |
| 100      | SSH         | `172.16.0.4/32` (jump from App) and/or office IP | 22   | Allow  |
| 110      | ProctorHttp | Internet **or** Gateway subnet                   | 8030 | Allow  |


---



## 3. DNS (when you have names)

Until Gateway exists:

- HR: `http://20.244.34.0:8030`
- Proctor: `http://<proctor-public-ip>:8030` after you attach a public IP

```
app.yourcompany.com      → Gateway public IP
proctor.yourcompany.com  → Gateway public IP
```

---



## 4. SSH and packages (Ubuntu 24.04 — both VMs)

Default Ubuntu 24.04 Python is **3.12**. This app is validated on **3.11**. Install 3.11 from the deadsnakes PPA.

```bash
sudo apt-get update
sudo apt-get install -y software-properties-common ca-certificates curl gnupg
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install -y git python3.11 python3.11-venv python3.11-dev \ 
     build-essential ffmpeg libpq-dev pkg-config
```

Node 20 LTS:

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Check:

```bash
python3.11 --version
node --version
npm --version
ffmpeg -version
git --version
```

**Postgres only on Interview-app:**

```bash
sudo apt-get install -y postgresql postgresql-contrib
```

Do **not** install PostgreSQL on Interview-Proctor.

---



## 5. PostgreSQL on Interview-app only (local disk)

```bash
sudo -u postgres psql
```

```sql
CREATE USER interview_app WITH PASSWORD 'Int@admrrg2026$';
CREATE DATABASE interview_scheduler OWNER interview_app;
GRANT ALL PRIVILEGES ON DATABASE interview_scheduler TO interview_app;
\q
```

Listen on localhost **and** the private NIC so Proctor (`172.17.0.4`) can connect:

```bash
ls /etc/postgresql/
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/*/main/postgresql.conf
echo "host interview_scheduler interview_app 172.17.0.4/32 scram-sha-256" | sudo tee -a /etc/postgresql/*/main/pg_hba.conf
echo "host interview_scheduler interview_app 127.0.0.1/32 scram-sha-256" | sudo tee -a /etc/postgresql/*/main/pg_hba.conf
sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

Test locally:

```bash
psql "postgresql://interview_app:choose-a-long-password@127.0.0.1:5432/interview_scheduler" -c 'SELECT 1'
```

Enable **Azure Backup** in vault **Interview-PRD-backup** for **Interview-app**.

---



## 6. Clone the repo (both VMs)

```bash
sudo mkdir -p /opt/apps
sudo chown "$USER:$USER" /opt/apps
cd /opt/apps
git clone https://github.com/ravimolake17/Interview_APP.git Interview_Agentic_AI
cd Interview_Agentic_AI
git checkout <production-branch>
```

Same commit on both machines.

---



## 7. Python venv (both VMs)

```bash
cd /opt/apps/Interview_Agentic_AI/backend
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

First install is slow (PyTorch CPU, Docling, Agent 5).

---



## 8. Frontend build (both VMs)

```bash
cd /opt/apps/Interview_Agentic_AI/frontend
npm install
npm run build
```

```bash
test -f /opt/apps/Interview_Agentic_AI/frontend/dist/index.html && echo HR_OK
test -f /opt/apps/Interview_Agentic_AI/backend/agent5_static/dist/index.html && echo A5_OK
```

App needs HR `frontend/dist`. Proctor needs `backend/agent5_static/dist`.

---



## 9. Agent 5 models (Proctor VM)

```bash
cd /opt/apps/Interview_Agentic_AI/backend
source venv/bin/activate
python -m scripts.agent5.prepare_models
```

```bash
df -h /
du -sh /opt/apps/Interview_Agentic_AI/models/agent5
```

---



## 10. Environment files

```bash
cd /opt/apps/Interview_Agentic_AI/backend
cp .env.example .env
nano .env
```

Generate secrets **once**; reuse the Agent 5 key on **both** VMs:

```bash
python3.11 -c "import secrets; print(secrets.token_urlsafe(48))"
```



### 10.1 Interview-app `/opt/apps/Interview_Agentic_AI/backend/.env`

```env
FRONTEND_URL=http://20.244.34.0:8030
DATABASE_URL=postgresql+asyncpg://interview_app:choose-a-long-password@127.0.0.1:5432/interview_scheduler
CHECKPOINT_DB_URL=postgresql://interview_app:choose-a-long-password@127.0.0.1:5432/interview_scheduler

JWT_SECRET_KEY=paste-app-jwt-secret
AGENT5_EMBEDDED=false
AGENT5_PUBLIC_URL=http://PROCTOR_PUBLIC_OR_GATEWAY_HOST:8030
AGENT5_SECRET_KEY=paste-same-agent5-secret-on-both-vms
AGENT5_CORS_ORIGINS=http://20.244.34.0:8030,http://PROCTOR_PUBLIC_OR_GATEWAY_HOST:8030
CORS_ORIGINS=http://20.244.34.0:8030,http://PROCTOR_PUBLIC_OR_GATEWAY_HOST:8030

SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=HR Team
SMTP_USE_TLS=true
SMTP_USE_SSL=false

LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://interview-azure-openai.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-10-21

SCREENING_QUEUE_ENABLED=true
SCREENING_EMBED_WORKERS=true
MAX_CONCURRENT_SCREENING_JOBS=20
LOG_LEVEL=INFO
```

When you have HTTPS hostnames, replace public URLs and CORS (no `:8030` if Gateway is on 443).

### 10.2 Interview-Proctor `/opt/apps/Interview_Agentic_AI/backend/.env`

Postgres host is App **private** IP `172.16.0.4`. No local database on Proctor.

```env
FRONTEND_URL=http://20.244.34.0:8030
DATABASE_URL=postgresql+asyncpg://interview_app:choose-a-long-password@172.16.0.4:5432/interview_scheduler
CHECKPOINT_DB_URL=postgresql://interview_app:choose-a-long-password@172.16.0.4:5432/interview_scheduler
AGENT5_DATABASE_URL=postgresql://interview_app:choose-a-long-password@172.16.0.4:5432/interview_scheduler

AGENT5_SECRET_KEY=paste-same-agent5-secret-on-both-vms
AGENT5_PUBLIC_URL=http://PROCTOR_PUBLIC_OR_GATEWAY_HOST:8030
AGENT5_CORS_ORIGINS=http://20.244.34.0:8030,http://PROCTOR_PUBLIC_OR_GATEWAY_HOST:8030
INTERVIEW_API_PUBLIC_URL=http://20.244.34.0:8030

AGENT5_STORAGE_DIR=/opt/apps/Interview_Agentic_AI/backend/storage/agent5
AGENT5_MODELS_DIR=/opt/apps/Interview_Agentic_AI/models/agent5
AGENT5_TEST_MODE=0
LOG_LEVEL=INFO
```

`INTERVIEW_API_PUBLIC_URL` is the URL the **candidate browser** uses for Agent 4 (App public IP or `https://app.yourcompany.com`).

---



## 11. Migrations (App VM only)

```bash
cd /opt/apps/Interview_Agentic_AI/backend
source venv/bin/activate
alembic upgrade head
```

Change the seeded SuperAdmin password immediately (see `.env.example`).

---



## 12. Test run (no reload, one worker)

**Interview-app**

```bash
cd /opt/apps/Interview_Agentic_AI/backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8030 --workers 1
```

```bash
curl -s http://127.0.0.1:8030/health/live
```

**Interview-Proctor**

```bash
cd /opt/apps/Interview_Agentic_AI/backend
source venv/bin/activate
uvicorn agents.proctoring_agent.main:app --host 0.0.0.0 --port 8030 --workers 1
```

```bash
curl -s http://127.0.0.1:8030/health/live
curl -s http://127.0.0.1:8030/api/runtime-config
```

From **Proctor**, Postgres on App must work:

```bash
psql "postgresql://interview_app:choose-a-long-password@172.16.0.4:5432/interview_scheduler" -c 'SELECT 1'
```

If this fails, fix NSG / `pg_hba` / `listen_addresses` before continuing.

---



## 13. systemd (Linux production)



### App — `/etc/systemd/system/interview-app.service`

```ini
[Unit]
Description=Interview Agentic AI app
After=network.target postgresql.service

[Service]
User=azureuser
Group=azureuser
WorkingDirectory=/opt/apps/Interview_Agentic_AI/backend
Environment=PYTHONPATH=/opt/apps/Interview_Agentic_AI/backend
ExecStart=/opt/apps/Interview_Agentic_AI/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8030 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```



### Proctor — `/etc/systemd/system/interview-proctor.service`

Same, but **no** `postgresql.service` and:

```ini
ExecStart=/opt/apps/Interview_Agentic_AI/backend/venv/bin/uvicorn agents.proctoring_agent.main:app --host 0.0.0.0 --port 8030 --workers 1
```

Use your SSH Linux user. Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now interview-app      # on App
sudo systemctl enable --now interview-proctor  # on Proctor
sudo systemctl status interview-app
```

---



## 14. Application Gateway (optional, HTTPS later)

Place it on `vnet-centralindia-1`:


| Listener host             | Backend           |
| ------------------------- | ----------------- |
| `app.yourcompany.com`     | `172.16.0.4:8030` |
| `proctor.yourcompany.com` | `172.17.0.4:8030` |


- Probe: `GET /health/live`
- Enable **WebSocket** on the Proctor HTTP setting
- Timeout ≥ 120s
- Do **not** put both VMs in one round-robin pool

---



## 15. SuperAdmin after first login

Open `http://20.244.34.0:8030` → SuperAdmin → **API & Integration**:


| Field             | Value                                                      |
| ----------------- | ---------------------------------------------------------- |
| Public app URL    | `http://20.244.34.0:8030` or `https://app.yourcompany.com` |
| Proctoring URL    | Proctor public URL                                         |
| Azure / Groq keys | paste here                                                 |


**LLM & AI:** Azure, deployment **gpt-4o** or **gpt-4o mini** only.

---



## 16. Verify

```bash
curl -s http://20.244.34.0:8030/health/live
curl -s http://PROCTOR_HOST:8030/health/live
curl -s http://PROCTOR_HOST:8030/api/runtime-config
```

1. HR login on App.
2. Screen, shortlist, send invite.
3. Join link must point at **Proctor** `/proctoring/`.
4. Camera on Proctor; Agent 4 questions hit App (`172.16.0.4` / public App URL).
5. App: Postgres rows. Proctor: files under `backend/storage/agent5`.
6. `df -h /` on Proctor after a test interview.

---



## 17. Update both VMs

```bash
cd /opt/apps/Interview_Agentic_AI
git pull
cd frontend && npm install && npm run build
cd ../backend
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head   # App VM
sudo systemctl restart interview-app       # App
sudo systemctl restart interview-proctor   # Proctor
```

---



## 18. Keep vs later


| Keep now                              | Later                         |
| ------------------------------------- | ----------------------------- |
| One VNet, two subnets, two IPs        | Application Gateway + HTTPS   |
| Local Postgres on Interview-app       | Azure Database for PostgreSQL |
| Recordings on Proctor local disk      | Data disk, then Blob          |
| Vault **Interview-PRD-backup** on App | Also back up Proctor          |
| Port 8030, `--workers 1`              | Redis / extra workers         |


**Do not**

- Install a second Postgres on Proctor
- Open 5432 to the internet
- `uvicorn --reload` or `--workers` > 1
- Rely on 9 PM auto-shutdown for live interviews

---



## 19. Command cheat sheet

```bash
# App
cd /opt/apps/Interview_Agentic_AI/backend
source venv/bin/activate
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8030 --workers 1

# Proctor
cd /opt/apps/Interview_Agentic_AI/backend
source venv/bin/activate
uvicorn agents.proctoring_agent.main:app --host 0.0.0.0 --port 8030 --workers 1

curl -s http://127.0.0.1:8030/health/live
```

