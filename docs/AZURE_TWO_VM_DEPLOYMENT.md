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



## 3. DNS + SSL (no Application Gateway — nginx on each VM)

Use this path for testing now. Application Gateway can replace nginx later (section 14).

**Hostnames:**


| Role     | Hostname               | Points to (A record)                  |
| -------- | ---------------------- | ------------------------------------- |
| HR / App | `intapp.rrglobal.com`  | App public IP `**20.244.34.0**`       |
| Proctor  | `proctor.rrglobal.com` | Proctor public IP `**4.247.180.216**` |


```
intapp.rrglobal.com    A    20.244.34.0
proctor.rrglobal.com   A    4.247.180.216
```



### SSL on nginx (not on uvicorn / systemd)

Uvicorn stays on **HTTP** `127.0.0.1:8030`. nginx listens on **443** with your certificate.

You need from IT (CSR alone is not enough):


| File                                     | Purpose                                          |
| ---------------------------------------- | ------------------------------------------------ |
| **Signed certificate** (`.crt` / `.cer`) | nginx `ssl_certificate`                          |
| **Private key**                          | nginx `ssl_certificate_key`                      |
| **Chain / intermediate** (if provided)   | append after leaf → `fullchain.crt`              |
| CSR                                      | already used to request the cert — not installed |


If one cert covers both names (SAN or `*.rrglobal.com`), use the same files on both VMs.

Ready-made configs: `deploy/nginx/intapp.conf` and `deploy/nginx/proctor.conf`.

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
psql 'postgresql://interview_app:Int%40admrrg2026%24@127.0.0.1:5432/interview_scheduler' -c 'SELECT 1'
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
psql "postgresql://interview_app:Int%40admrrg2026%24@172.16.0.4:5432/interview_scheduler" -c 'SELECT 1'
```

If this fails, fix NSG / `pg_hba` / `listen_addresses` before continuing.

---



## 13. systemd (Linux production)

**Prerequisite:** Section 12 tests passed (`health/live`, Proctor `runtime-config`, Proctor → Postgres `SELECT 1`).

SSH user on these VMs: `**Interview-Administrator**`.  
Stop any foreground `uvicorn` (**Ctrl+C**) on that VM before enabling systemd — only one process may bind port 8030.

**No** `source venv/bin/activate` **in systemd** — `ExecStart` uses `venv/bin/uvicorn` directly.  
**No SSL in these files** — certificates go on Application Gateway (section 14).

### App — create `/etc/systemd/system/interview-app.service`

```bash
sudo tee /etc/systemd/system/interview-app.service >/dev/null <<'EOF'
[Unit]
Description=Interview Agentic AI app (intapp.rrglobal.com)
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=Interview-Administrator
Group=Interview-Administrator
WorkingDirectory=/opt/apps/Interview_Agentic_AI/backend
Environment=PYTHONPATH=/opt/apps/Interview_Agentic_AI/backend
EnvironmentFile=/opt/apps/Interview_Agentic_AI/backend/.env
ExecStart=/opt/apps/Interview_Agentic_AI/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8030 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now interview-app
sudo systemctl status interview-app --no-pager
```



### Proctor — create `/etc/systemd/system/interview-proctor.service`

```bash
sudo tee /etc/systemd/system/interview-proctor.service >/dev/null <<'EOF'
[Unit]
Description=Interview Agentic AI proctor (proctor.rrglobal.com)
After=network.target

[Service]
Type=simple
User=Interview-Administrator
Group=Interview-Administrator
WorkingDirectory=/opt/apps/Interview_Agentic_AI/backend
Environment=PYTHONPATH=/opt/apps/Interview_Agentic_AI/backend
EnvironmentFile=/opt/apps/Interview_Agentic_AI/backend/.env
ExecStart=/opt/apps/Interview_Agentic_AI/backend/venv/bin/uvicorn agents.proctoring_agent.main:app --host 0.0.0.0 --port 8030 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now interview-proctor
sudo systemctl status interview-proctor --no-pager
```

Useful commands:

```bash
sudo systemctl restart interview-app      # App
sudo systemctl restart interview-proctor  # Proctor
sudo journalctl -u interview-app -f
sudo journalctl -u interview-proctor -f
```

---



## 13b. nginx + hostnames (no Application Gateway — use this for testing)

**Topology**

```
Browser → https://intapp.rrglobal.com:443  → nginx (App VM)     → 127.0.0.1:8030 uvicorn
Browser → https://proctor.rrglobal.com:443 → nginx (Proctor VM) → 127.0.0.1:8030 uvicorn
Proctor → Postgres on App private IP 172.16.0.4:5432 (unchanged)
```



### A. DNS (IT / DNS admin)

```
intapp.rrglobal.com    A    20.244.34.0
proctor.rrglobal.com   A    4.247.180.216
```

Wait for propagation (`nslookup intapp.rrglobal.com`).

### B. NSG inbound (both VMs)


| NSG                   | Rule                  | Port              | Source                                    |
| --------------------- | --------------------- | ----------------- | ----------------------------------------- |
| Interview-app-nsg     | `AppHttps`            | **443**           | Internet                                  |
| Interview-app-nsg     | `AppHttpRedirect`     | **80** (optional) | Internet                                  |
| Interview-Proctor-nsg | `ProctorHttps`        | **443**           | Internet                                  |
| Interview-Proctor-nsg | `ProctorHttpRedirect` | **80** (optional) | Internet                                  |
| Interview-Proctor-nsg | `ProctorHttp`         | **8030**          | optional — only if you still test IP:8030 |


After nginx works, you can **remove Internet → 8030** and leave only 443 (uvicorn stays local).

### C. Install nginx + place certificates (both VMs)

```bash
sudo apt-get update
sudo apt-get install -y nginx
sudo mkdir -p /etc/ssl/rrglobal
sudo chmod 700 /etc/ssl/rrglobal
```

Copy your **signed cert** and **private key** onto each VM (SCP / Portal — never commit):

```bash
# App example names — adjust to what IT gave you
sudo nano /etc/ssl/rrglobal/intapp.fullchain.crt   # leaf + intermediates
sudo nano /etc/ssl/rrglobal/intapp.key              # BEGIN PRIVATE KEY
sudo chmod 600 /etc/ssl/rrglobal/intapp.key
```

Proctor: same pattern with `proctor.fullchain.crt` / `proctor.key` (or same wildcard files).

### D. App VM — enable site

```bash
sudo cp /opt/apps/Interview_Agentic_AI/deploy/nginx/intapp.conf /etc/nginx/sites-available/intapp
# If repo path differs, paste the file from the laptop deploy/nginx/intapp.conf
sudo ln -sf /etc/nginx/sites-available/intapp /etc/nginx/sites-enabled/intapp
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```



### E. Proctor VM — enable site (WebSocket)

```bash
sudo cp /opt/apps/Interview_Agentic_AI/deploy/nginx/proctor.conf /etc/nginx/sites-available/proctor
sudo ln -sf /etc/nginx/sites-available/proctor /etc/nginx/sites-enabled/proctor
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```



### F. `.env` (HTTPS hostnames — no :8030)

Already correct in `deploy/vm-env/interview.env` and `proctor.env`:

```env
FRONTEND_URL=https://intapp.rrglobal.com
AGENT5_PUBLIC_URL=https://proctor.rrglobal.com
INTERVIEW_API_PUBLIC_URL=https://intapp.rrglobal.com
CORS_ORIGINS=https://intapp.rrglobal.com,https://proctor.rrglobal.com
AGENT5_CORS_ORIGINS=https://intapp.rrglobal.com,https://proctor.rrglobal.com
```

Copy to each VM `backend/.env`, then:

```bash
sudo systemctl restart interview-app      # App
sudo systemctl restart interview-proctor  # Proctor
```



### G. Verify

```powershell
curl.exe -s https://intapp.rrglobal.com/health/live
curl.exe -s https://proctor.rrglobal.com/health/live
curl.exe -s https://proctor.rrglobal.com/api/runtime-config
```

Browser: `https://intapp.rrglobal.com` → login → SuperAdmin URLs same hostnames.

**Later:** Application Gateway can replace nginx; keep the same hostnames and only change DNS A records to the Gateway IP.

---



## 14. Application Gateway (recommended production path — full Portal steps)



### Answer first: do you need a 3rd subnet?

**Yes.** Keep your existing two subnets for the VMs. Add a **dedicated** third subnet only for Application Gateway.


| Subnet (existing / new) | CIDR (yours)         | Used by                                                    |
| ----------------------- | -------------------- | ---------------------------------------------------------- |
| `snet-centralindia-1`   | `172.16.0.0/24`      | Interview-app (`172.16.0.4`) — **do not put AGW here**     |
| `snet-centralindia-2`   | `172.17.0.0/24`      | Interview-Proctor (`172.17.0.4`) — **do not put AGW here** |
| `**snet-appgw**` (new)  | e.g. `172.18.0.0/24` | Application Gateway only                                   |


Azure Application Gateway **v2 needs its own empty subnet**. That subnet **must not** contain VMs.

> **Name warning:** Do **not** name it `GatewaySubnet`. In the Portal that name is reserved for **Virtual Network Gateway** (VPN / ExpressRoute). Application Gateway uses a **normal Default subnet** with any other name (e.g. `snet-appgw`).



### Subnet purpose in the “Add a subnet” blade


| Field                               | What to set                                                  |
| ----------------------------------- | ------------------------------------------------------------ |
| **Subnet purpose**                  | `**Default`**                                                |
| **Name**                            | `**snet-appgw`** (or `agw-subnet` — **not** `GatewaySubnet`) |
| **Include an IPv4 address space**   | **Checked** — pick a free range such as `**172.18.0.0/24`**  |
| **Enable private subnet**           | **Uncheck** (AGW needs outbound access)                      |
| **NAT gateway / Route table / NSG** | Leave empty unless your manager says otherwise               |
| **Delegation**                      | None                                                         |


If the Portal says *“Please select Virtual Network Gateway… to use the name GatewaySubnet”* — change the **name**; do not switch purpose to Virtual Network Gateway (that is for VPN, not App Gateway).

If `**172.18.0.0/24` is not offered**, expand VNet **Address space** first (with manager approval), then add the subnet.

---



### Goal (after Gateway is live)

```
Internet → https://intapp.rrglobal.com  ──┐
Internet → https://proctor.rrglobal.com ──┼─→ Application Gateway (public IP, SSL :443)
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
           App 172.16.0.4:8030 HTTP                  Proctor 172.17.0.4:8030 HTTP
                    (uvicorn / systemd)                         (uvicorn / systemd)
```

- SSL terminates on the **Gateway** (not on uvicorn, not required on nginx).
- Both DNS names point to the **same Gateway public IP**; SNI chooses App vs Proctor.
- Ignore empty route table `Vnet-firewall-Interview-PRD` until your manager adds routes + associations.

---



### Prerequisites

1. Both apps healthy via systemd:
  ```bash
   curl -s http://127.0.0.1:8030/health/live
  ```
2. From IT: **PFX** (password-protected) covering `intapp.rrglobal.com` **and** `proctor.rrglobal.com` (or `*.rrglobal.com`). A CSR alone is not enough.
3. RG `Interview-PRD-RG`, VNet `vnet-centralindia-1`, region **Central India**.
4. Manager OK to create `snet-appgw` + Application Gateway cost.

---



### Step 1 — Create Application Gateway subnet (you are here)

1. Portal → **Virtual networks** → `**vnet-centralindia-1`** → **Subnets** → **+ Subnet**.
2. **Subnet purpose:** `Default`.
3. **Name:** `snet-appgw` (**not** `GatewaySubnet`).
4. **Check** “Include an IPv4 address space” → set `**172.18.0.0/24`** (or free range).
5. **Uncheck** “Enable private subnet…”.
6. Leave NSG / route table / NAT empty.
7. Click **Add**.

You should now see **3 subnets**: `snet-centralindia-1`, `snet-centralindia-2`, `snet-appgw`.

---



### Step 2 — Create Application Gateway (wizard)

1. Portal → **Create a resource** → search **Application Gateway** → **Create**.



#### Basics


| Setting                  | Value                                                   |
| ------------------------ | ------------------------------------------------------- |
| Subscription             | RRKabel-Digital-Projects                                |
| Resource group           | `Interview-PRD-RG`                                      |
| Application gateway name | `agw-interview-prd`                                     |
| Region                   | **Central India**                                       |
| Tier                     | **Standard V2** (or **WAF V2** if security requires)    |
| Enable autoscaling       | Yes — Min **1**, Max **2** (or fixed 1–2 for test)      |
| Availability zone        | Zone-redundant if offered, else None                    |
| Virtual network          | `vnet-centralindia-1`                                   |
| Subnet                   | `**snet-appgw**` (the dedicated AGW subnet from Step 1) |




#### Frontends


| Setting                  | Value                                         |
| ------------------------ | --------------------------------------------- |
| Frontend IP address type | **Public**                                    |
| Public IP address        | **Create new** → name `agw-interview-prd-pip` |




#### Backends

Add **two** backend pools (**Add** twice). Do **not** put both VMs in one pool.


| Backend pool name | Target type        | Targets      |
| ----------------- | ------------------ | ------------ |
| `pool-intapp`     | IP address or FQDN | `172.16.0.4` |
| `pool-proctor`    | IP address or FQDN | `172.17.0.4` |




#### Configuration (routing rule in wizard)

The create wizard often forces **one** rule. Create a temporary rule so create can finish; you will fix multi-site in Steps 4–7:


| Setting          | Temporary value                                                              |
| ---------------- | ---------------------------------------------------------------------------- |
| Rule name        | `rule-temp-intapp`                                                           |
| Priority         | `100`                                                                        |
| Listener         | HTTPS 443, Multi-site, host `intapp.rrglobal.com` (upload PFX here if asked) |
| Backend target   | `pool-intapp`                                                                |
| Backend settings | HTTP, port **8030**, timeout **120**                                         |


If the wizard will not accept the cert yet, create with HTTP listener temporarily, then convert to HTTPS after create (not ideal for production — prefer uploading PFX in the wizard).

#### Tags → Review + create

Wait until the Gateway shows **Succeeded** (~10–20 minutes).  
Open **Overview** → copy **Frontend public IP address** (you will give this to DNS).

---



### Step 3 — Health probes

Gateway → **Settings** → **Health probes** → **Add** (two probes):

`**probe-intapp**`


| Setting                                  | Value                                                              |
| ---------------------------------------- | ------------------------------------------------------------------ |
| Protocol                                 | HTTP                                                               |
| Host                                     | Leave empty **or** use “Pick host name from backend HTTP settings” |
| Path                                     | `/health/live`                                                     |
| Interval / Timeout / Unhealthy threshold | 30 / 30 / 3                                                        |
| Use probe matching backend settings      | Yes, when linking later                                            |


`**probe-proctor**` — same path `/health/live`.

---



### Step 4 — Backend settings (HTTP to uvicorn)

Gateway → **Settings** → **Backend settings** → **Add** (two):

`**setting-intapp-http**`


| Setting                     | Value          |
| --------------------------- | -------------- |
| Backend protocol            | **HTTP**       |
| Backend port                | **8030**       |
| Cookie-based affinity       | Disabled       |
| Connection draining         | Optional       |
| Request time-out (seconds)  | **120**        |
| Override with new host name | **No**         |
| Custom probe                | `probe-intapp` |


`**setting-proctor-http**`


| Setting                     | Value                                |
| --------------------------- | ------------------------------------ |
| Backend protocol            | **HTTP**                             |
| Backend port                | **8030**                             |
| Request time-out (seconds)  | **300** (WebSocket / long interview) |
| Override with new host name | **No**                               |
| Custom probe                | `probe-proctor`                      |


Application Gateway v2 forwards WebSocket upgrades on HTTP settings by default. Do not force HTTPS to the backend unless you terminate TLS on the VM (you are not).

---



### Step 5 — SSL certificate

Gateway → **Listeners** → **Listener TLS certificates** (or **SSL certificates**) → **Add**:


| Setting               | Value                     |
| --------------------- | ------------------------- |
| Name                  | `cert-rrglobal-interview` |
| Create new / Existing | Upload certificate (.pfx) |
| PFX file + password   | From IT                   |


Build PFX only if IT gave `.crt` + `.key` (on a secure admin PC — never commit):

```powershell
openssl pkcs12 -export -out interview.pfx -inkey private.key -in signed.crt -certfile chain.crt
```

---



### Step 6 — Listeners (multi-site HTTPS)

Gateway → **Listeners** → **Add** (two listeners). Delete any temporary HTTP-only listener you no longer need.


| Name                   | Frontend IP | Port | Protocol | Listener type  | Host name              | Certificate               |
| ---------------------- | ----------- | ---- | -------- | -------------- | ---------------------- | ------------------------- |
| `listen-intapp-https`  | Public      | 443  | HTTPS    | **Multi site** | `intapp.rrglobal.com`  | `cert-rrglobal-interview` |
| `listen-proctor-https` | Public      | 443  | HTTPS    | **Multi site** | `proctor.rrglobal.com` | same                      |


Optional: listeners on port **80** with **Redirect** → corresponding HTTPS listener (HTTP → HTTPS).

---



### Step 7 — Request routing rules

Gateway → **Rules** → **Add** (two **Basic** rules). Remove or repoint the temporary wizard rule.


| Rule name      | Priority | Listener               | Backend target | Backend settings       |
| -------------- | -------- | ---------------------- | -------------- | ---------------------- |
| `rule-intapp`  | 100      | `listen-intapp-https`  | `pool-intapp`  | `setting-intapp-http`  |
| `rule-proctor` | 200      | `listen-proctor-https` | `pool-proctor` | `setting-proctor-http` |


Confirm **Backend health** shows both pools **Healthy**.

---



### Step 8 — NSG (Gateway → VM :8030)

Gateway reaches VMs on the **private** VNet. Ensure both NSGs allow 8030 from the VNet / Gateway subnet.

**Interview-app-nsg** — add or keep:


| Priority | Name           | Source                                               | Port | Action |
| -------- | -------------- | ---------------------------------------------------- | ---- | ------ |
| 110      | AppFromGateway | `172.18.0.0/24` (`snet-appgw`) **or** VirtualNetwork | 8030 | Allow  |


**Interview-Proctor-nsg** — add:


| Priority | Name               | Source                                               | Port | Action |
| -------- | ------------------ | ---------------------------------------------------- | ---- | ------ |
| 110      | ProctorFromGateway | `172.18.0.0/24` (`snet-appgw`) **or** VirtualNetwork | 8030 | Allow  |


`AllowVnetInBound` (default) often already allows this. After HTTPS works via Gateway, you may **remove Internet → 8030** so candidates only use `:443` on the Gateway.

---



### Step 9 — DNS (IT)

Point **both** A records to the **Application Gateway frontend public IP** (not App `20.244.34.0`, not Proctor `4.247.180.216`):

```
intapp.rrglobal.com    A    <agw-interview-prd public IP>
proctor.rrglobal.com   A    <same agw public IP>
```

Wait for DNS: `nslookup intapp.rrglobal.com`.

---



### Step 10 — `.env` on both VMs

```env
FRONTEND_URL=https://intapp.rrglobal.com
AGENT5_PUBLIC_URL=https://proctor.rrglobal.com
INTERVIEW_API_PUBLIC_URL=https://intapp.rrglobal.com
CORS_ORIGINS=https://intapp.rrglobal.com,https://proctor.rrglobal.com
AGENT5_CORS_ORIGINS=https://intapp.rrglobal.com,https://proctor.rrglobal.com
AGENT5_EMBEDDED=false
```

```bash
sudo systemctl restart interview-app      # App
sudo systemctl restart interview-proctor  # Proctor
```

---



### Step 11 — SuperAdmin + verify

Browser: `https://intapp.rrglobal.com` → SuperAdmin → **API & Integration**:

- Public app URL = `https://intapp.rrglobal.com`
- Proctoring URL = `https://proctor.rrglobal.com`

```powershell
curl.exe -s https://intapp.rrglobal.com/health/live
curl.exe -s https://proctor.rrglobal.com/health/live
curl.exe -s https://proctor.rrglobal.com/api/runtime-config
```

Expect `interview_api_origin` = `https://intapp.rrglobal.com`.

---



### Troubleshooting


| Symptom                                    | Fix                                                                  |
| ------------------------------------------ | -------------------------------------------------------------------- |
| Cannot select AGW subnet when creating AGW | Create `snet-appgw` first; do not use name `GatewaySubnet`           |
| Address range not available                | Expand VNet **Address space**, then add subnet                       |
| Backend Unhealthy                          | uvicorn down; probe `/health/live`; NSG blocks 8030; wrong pool IP   |
| 502                                        | Same as unhealthy; check Backend health blade                        |
| Certificate error in browser               | PFX must include both hostnames (SAN) or wildcard                    |
| Interview room / camera fails              | Use `https://proctor.rrglobal.com`; increase Proctor timeout to 300s |
| Wrong app on a hostname                    | Multi-site listeners + correct host names; DNS both to AGW IP        |




### Optional later

- Stop using VM public IPs for candidates (keep for SSH if needed).
- Disable nginx if you installed the interim path (section 13b).
- Wire `Vnet-firewall-Interview-PRD` only when manager provides Azure Firewall next-hop + associates subnets.

---



## 15. SuperAdmin after first login

Open `https://intapp.rrglobal.com` → SuperAdmin → **API & Integration**:


| Field             | Value                          |
| ----------------- | ------------------------------ |
| Public app URL    | `https://intapp.rrglobal.com`  |
| Proctoring URL    | `https://proctor.rrglobal.com` |
| Azure / Groq keys | paste here                     |


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

