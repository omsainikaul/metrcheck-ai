# MetrCheck AI — Docker Deployment Guide

MetrCheck AI (PS 26034) is fully containerized using a two-container Docker architecture:
1. **Backend Service (`metrcheck-backend`)**: Python 3.11 FastAPI with PaddleOCR deep learning engine (PP-OCRv4), SQLite database (aiosqlite), and rule compliance checking.
2. **Frontend Service (`metrcheck-frontend`)**: Production React + TypeScript application built with Vite, served via an optimized Nginx Alpine image acting as a reverse proxy for `/api/` and `/uploads/`.

---

## 1. Prerequisites

- **Docker Desktop** (Windows / macOS) or **Docker Engine + Docker Compose** (Linux)
- **Hardware**: Standard x86_64 / ARM64 CPU (No GPU or CUDA required; inference runs on CPU)

---

## 2. Quickstart (2 Commands)

From the project root directory:

```bash
# 1. Build and start all services in the foreground
docker compose up --build
```

*(Optional: Run in detached mode in the background)*
```bash
docker compose up -d --build
```

To stop the services at any time:
```bash
docker compose down
```

---

## 3. Application URLs & Endpoints

| Component | URL | Purpose |
|---|---|---|
| **Web Application** | [http://localhost:8080](http://localhost:8080) | Full React UI (Dashboard, Multi-angle Analysis, History, Admin) |
| **API Health Check (via Nginx)** | [http://localhost:8080/api/health](http://localhost:8080/api/health) | Backend status, OCR engine check & DB connectivity via reverse proxy |
| **Standalone Backend (Local Dev)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI when running backend locally (`uvicorn main:app --port 8000`) |
| **OpenAPI Schema (via Nginx)** | [http://localhost:8080/api/openapi.json](http://localhost:8080/api/openapi.json) | Raw OpenAPI JSON specification |

---

## 4. Default Login & Demonstration Accounts
 
In demonstration mode (`METRCHECK_DEMO_MODE=true`), operational demo accounts are seeded automatically:
 
| Username | Password | Role | Description |
|---|---|---|---|
| `officer` | `officer123` | `ENFORCEMENT_OFFICER` | Enforcement Officer (Analysis, penalty assessment, notices) |
| `audit` | `audit123` | `AUDIT_OFFICER` | Quality & Compliance Inspector (Technical verification) |
| `merchant` | `merchant123` | `MERCHANT_PUBLIC` | Demo Brand / Merchant (Pre-flight label self-audit) |
 
*System Administrators are provisioned securely via `python -m backend.scripts.bootstrap_admin` or `python -m backend.scripts.change_admin_credentials`. Admin passwords are never seeded or stored in plaintext.*

---

## 5. Data Persistence

All stateful data is persisted on the host filesystem under `./data/` (mounted into `/data` inside the backend container):

```
data/
├── metrc_check.db    # SQLite database (Users, Analyses, Audit History)
└── uploads/          # Uploaded product packaging images and evidence
```

- **Persistence**: Rebuilding or restarting containers preserves all previous analyses, history, and users.
- **Resetting State**: To reset the database and clear all uploads, stop the containers and delete the `./data` folder:
  ```bash
  docker compose down
  # Windows PowerShell:
  Remove-Item -Recurse -Force ./data
  # Linux / macOS:
  rm -rf ./data
  ```

---

## 6. Configuration & Environment Variables

Environment variables can be customized in `docker-compose.yml` or via a `.env` file at the project root:

| Variable | Default Value | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production-secure-key` | JWT token secret key for signing authentication tokens |
| `OCR_ENGINE` | `paddleocr` | OCR engine: `paddleocr` (PP-OCRv4 deep learning engine) |
| `LLM_API_KEY` | *(empty)* | Optional Google Gemini API key for hybrid LLM extraction |
| `UPLOAD_DIR` | `/data/uploads` | Absolute container path for media storage |
| `DATABASE_PATH` | `/data/metrc_check.db` | Absolute container path for SQLite database |
| `PYTHONUNBUFFERED` | `1` | Ensures real-time logging output from Python |

### Changing the Secret Key
Edit `docker-compose.yml` under the `backend.environment` section:
```yaml
environment:
  - SECRET_KEY=your-secure-random-secret-key-here
```

---

## 7. Troubleshooting

### Port Conflicts (Port 8080 or 8000 already in use)
If port 8080 or 8000 is occupied by another application on your host machine:
1. Open `docker-compose.yml`.
2. Change the host port mapping:
   - For frontend: `"8081:80"` (access at `http://localhost:8081`)
   - For backend: `"8001:8000"` (access at `http://localhost:8001`)

### OneDrive / Network Drive Disk Latency Note
If running the project from a directory synced with Microsoft OneDrive or a networked file share, SQLite file locking and disk I/O may encounter occasional latency.
- **Recommendation**: For optimal speed, run Docker from a local un-synced folder (e.g., `C:\projects\metrcheck` or your local home directory).

### Inspecting Logs
```bash
# View aggregated real-time logs
docker compose logs -f

# View backend logs only
docker compose logs -f backend

# View frontend / Nginx logs only
docker compose logs -f frontend
```

---

## 8. Report Exports, Download Tickets & SMTP Configuration

### Multi-Format Report Exports

MetrCheck AI generates compliance audit reports in four formats, available from any analysis results page:

| Format | Endpoint | Description |
|---|---|---|
| **PDF** | `GET /api/report/{analysis_id}.pdf` | Formal GoI/DoCA-style statutory inspection dossier with embedded evidence thumbnail and QR verification code |
| **Excel (XLSX)** | `GET /api/report/{analysis_id}.xlsx` | Multi-tab spreadsheet for departmental audit registers |
| **CSV** | `GET /api/report/{analysis_id}.csv` | Machine-readable export for integration with enforcement databases |
| **JSON** | `GET /api/report/{analysis_id}.json` | Structured data export for API consumers and automated pipelines |

All report endpoints enforce the same tenant isolation and authorization checks as the analysis API — a user can only download reports for their own organization's analyses.

### Secure Download Ticket Mechanism

For browser-side file downloads (triggered by UI buttons), MetrCheck AI uses a secure, single-use **download ticket** system to avoid embedding Bearer tokens in URL query strings:

1. The frontend requests a short-lived ticket via `POST /api/report/ticket`.
2. The server returns a one-time-use token valid for 60 seconds.
3. The frontend appends the ticket to the download URL: `GET /api/report/{id}.pdf?ticket=<token>`.
4. The ticket is consumed on first use and cannot be replayed.

This eliminates the need to expose authentication tokens in server logs, browser history, or HTTP referrer headers.

### SMTP Configuration (Officer Invitation & Password Recovery Emails)

The system sends transactional emails for:
- Officer account invitation (access provisioning flow)
- Password reset links

SMTP is configured via environment variables. **Never hardcode real credentials in source code, `.env` files committed to Git, or Docker image layers.**

**For local/dev:** Set in `backend/.env` (gitignored):
```
METRCHECK_SMTP_HOST=smtp.gmail.com
METRCHECK_SMTP_PORT=587
METRCHECK_SMTP_USER=your-email@gmail.com
METRCHECK_SMTP_PASS=your-app-password
METRCHECK_SMTP_FROM=your-email@gmail.com
METRCHECK_SMTP_TLS=true
```

**For Docker:** Set via `docker-compose.yml` environment section or Docker secrets:
```yaml
environment:
  - METRCHECK_SMTP_HOST=smtp.example.com
  - METRCHECK_SMTP_PORT=587
  - METRCHECK_SMTP_USER=${SMTP_USER}        # injected from host environment
  - METRCHECK_SMTP_PASS=${SMTP_PASS}        # injected from host environment
  - METRCHECK_SMTP_TLS=true
```

> **Security Note:** Gmail App Passwords must be generated through Google Account → Security → App Passwords. The password grants email-send access to the account — rotate it immediately if it is ever accidentally exposed in logs, source control, or bug reports.

### Docker Secret & Environment Best Practices

| Practice | Details |
|---|---|
| **`.dockerignore`** | The project includes a `.dockerignore` file that explicitly excludes `.env`, `backend/.env`, `*.db`, `venv/`, `venv311/`, and `node_modules/` from the Docker build context. |
| **No secrets in images** | Never use `ENV SMTP_PASS=...` inside a `Dockerfile` — this bakes secrets into the image layer and they appear in `docker inspect`. |
| **Inject at runtime** | Pass secrets via `docker run -e` or Docker Compose `environment:` with host-environment variable references (`${VAR}`). |
| **Production SECRET_KEY** | The application validates at startup that `SECRET_KEY` is not a default/placeholder in production environments. Set a minimum 32-character random string. |

