# MetrCheck AI

**AI-Assisted Smart Automation Platform for Packaged-Product Compliance**  
*National Hackathon 6.0 | Smart India Hackathon 2026 — Problem Statement: SIH26202 (Student Innovation)*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-blue?logo=react&logoColor=white)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0%2B-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4.x-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)

---

## Overview

**MetrCheck AI** is an AI-assisted smart automation platform for packaged-product compliance. It combines product images, OCR, computer vision, regulatory rules, and verification sources to extract structured information, evaluate compliance, generate evidence, and support human officer verification and enforcement workflows.

By pairing Optical Character Recognition (OCR) with deterministic rule evaluation, computer vision bounding boxes, and multi-role human-in-the-loop verification, MetrCheck AI detects mandatory packaging declarations (such as MRP, Net Quantity, Manufacturer details, Dates, and Customer Care contacts), identifies omissions or formatting defects, and generates an explainable compliance score and audit report.

---

## SIH 2026 Alignment

| Field | Details |
|---|---|
| **Problem Statement** | **SIH26202** |
| **Organization** | **AICTE** |
| **Category** | **Software** |
| **Theme** | **Smart Automation** |
| **Problem Statement Title** | **Student Innovation** |

### How MetrCheck AI Addresses the SIH26202 Concept

The **SIH26202** problem statement focuses on the intelligent use of resources for technological advancement by combining artificial intelligence, exploring multiple sources, and obtaining valuable insights.

**MetrCheck AI** applies this smart automation concept to an end-to-end packaged-product compliance workflow by orchestrating multiple data streams and AI capabilities:

**Sources & Inputs:**
- **Product Packaging Images**: Multi-angle visual labels from retail packaging and e-commerce listings.
- **OCR Text & Spatial Coordinates**: Deep-learning text detection (DBNet) and character recognition (SVTR) via PaddleOCR.
- **Computer Vision Detections**: Spatial boundary mapping, bounding boxes, and evidence cropping.
- **Structured Product Information**: Brand names, product categories, SKU codes, and merchant catalog metadata.
- **Regulatory Rules**: Codified statutory clauses from the Legal Metrology (Packaged Commodities) Rules, 2011.
- **FSSAI Verification Data**: License number pattern validation and regulatory verification where configured.
- **GS1 / GTIN Verification Data**: Barcode (EAN-13, UPC, QR) format and check-digit validation.
- **Human Officer Verification**: Audit Officer reviews, evidence validation, and field-level corrections.

**Automated Outputs & Value:**
- **Structured Product Information**: Standardized extraction of MRP, Net Quantity, Dates, Manufacturer/Packer addresses, Consumer Care contacts, and Country of Origin.
- **Compliance Findings**: Instant clause-by-clause evaluation against mandatory statutory rules.
- **Explainable Risk Indicators**: Clear scoring (0–100) with color-coded classification (Compliant, Warning, Violation).
- **Evidence-Backed Results**: Visual bounding-box overlays linked to specific rule evaluations in the Evidence Viewer.
- **Human Verification Records**: Immutable snapshots preserving AI analysis alongside human officer corrections and audit logs.
- **Comprehensive Compliance Reports**: Multilingual PDF and digital audit reports generated across 10 Indic languages and English.
- **Enforcement Case Docket**: Automatic case escalation and workflow tracking for non-compliant commodities requiring formal statutory action.

---

## Application Domain: Legal Metrology & Packaged Commodity Compliance

Under the Indian Legal Metrology Act and the Legal Metrology (Packaged Commodities) Rules, 2011, all pre-packaged commodities sold across offline retail and e-commerce platforms must carry explicit mandatory declarations to safeguard consumer rights.

### The Challenge
Manual verification of packaging labels is:
- **Time-Intensive & Expensive**: Inspecting thousands of SKUs across physical retail and e-commerce requires substantial human labor.
- **Error-Prone**: Minor omissions, font size discrepancies, ambiguous addresses, and improper metric units frequently slip past manual review.
- **Inconsistent**: Different inspectors may apply varying levels of scrutiny.

There is a critical need for an automated, objective, AI-driven inspection pipeline capable of ingesting packaging images, extracting declaration text with spatial coordinates, evaluating rules, and flagging non-compliant products instantly while supporting human officer verification and enforcement workflows.

---

## Solution Pipeline

MetrCheck AI implements an end-to-end multi-stage pipeline:

$$\text{Product Image} \longrightarrow \text{OCR Engine} \longrightarrow \text{Information Extraction} \longrightarrow \text{Compliance Check} \longrightarrow \text{Score} \longrightarrow \text{Human Review} \longrightarrow \text{Enforcement}$$

1. **Image Ingestion**: Accepts label images via drag-and-drop or sample selection.
2. **OCR Engine**: Detects raw text fragments and extracts 2D bounding boxes using PaddleOCR (PP-OCRv4 deep learning engine).
3. **Information Extraction**: Employs pattern recognition (regex) and structured parsing to extract key packaging attributes:
   - Maximum Retail Price (MRP inclusive of all taxes)
   - Net Quantity (metric weight, volume, or count)
   - Date of Manufacture / Packing / Import
   - Expiry Date / Best Before period
   - Manufacturer / Packer / Importer Name & Physical Address
   - Consumer Care Details (Phone & Email)
   - Country of Origin
4. **Compliance Check**: Validates extracted data against codified Legal Metrology rules and mandatory declaration requirements.
5. **Scoring & Explainability**: Generates a standardized compliance score (0–100) alongside fine-grained classification:
   - **Compliant**: Mandatory declarations present and valid.
   - **Warning**: Declarations present with non-critical formatting ambiguities or missing optional fields.
   - **Violation**: Missing mandatory declarations or non-standard representations.
6. **Human Verification & Escalation**: Human Audit Officers review findings, correct extracted values, and escalate critical non-compliance to Enforcement Officers.
7. **Report Generation**: Presents visual bounding-box highlights, field-by-field verdicts, and downloadable inspection audit reports in multiple languages.

---

## Workspaces & Operational Roles

MetrCheck AI provides dedicated, role-isolated workspaces tailored to each stakeholder in the compliance lifecycle:

### 1. Consumer Workspace
- **Product Compliance Check**: Instant drag-and-drop packaging label scanning and compliance scoring.
- **Manual Product Check**: Guided form-based compliance checking with sample preset loaders.
- **Scan History**: Complete historical record of consumer scans with status badges.
- **Multilingual Reports**: Downloadable compliance reports in 10 Indic languages and English.

### 2. Merchant Workspace
- **Product Catalog Management**: SKU creation, variant tracking, barcode mapping, and packaging asset storage.
- **Pre-Print Packaging Verification**: Early compliance validation before committing packaging designs to physical print runs.
- **Listing Check**: E-commerce catalog text and declaration verification against statutory requirements.
- **Version Comparison**: Side-by-side compliance diffing between packaging revisions and iterations.

### 3. Audit Officer Workspace (Human-in-the-Loop)
- **Officer Review Queue**: Centralized review inbox for packaging analyses requiring human validation.
- **Human Verification Workflow**: Formal review state machine (`PENDING_REVIEW` → `IN_REVIEW` → `VERIFIED` / `REJECTED` / `ESCALATED`).
- **Evidence Inspection & Correction**: Interactive visual Evidence Viewer with field-level correction capabilities.
- **AI vs. Human Comparison**: Clear side-by-side comparison tracking human modifications against original AI extractions.
- **Case Escalation**: Seamless handoff from audit verification to statutory enforcement upon detecting critical violations.

### 4. Enforcement Officer Workspace
- **Enforcement Case Docket**: Dedicated case management workspace for escalated non-compliant commodities.
- **Case Assignment & Ownership**: Track active cases assigned to specific enforcement officers.
- **Investigation Log & Notices**: Record investigation notes, statutory notices, and penalty reviews under the Legal Metrology Act.
- **Case Resolution Lifecycle**: Full case state machine (`DRAFT` → `NOTICE_ISSUED` → `HEARING_SCHEDULED` → `RESOLVED` / `DISMISSED`).

### 5. Admin Governance Workspace
- **User Management & Provisioning**: Secure provisioning, role management, and lifecycle controls for Audit and Enforcement officers.
- **Officer Requests**: Review and approval workflows for officer registration requests.
- **Security Audit Logs**: Tamper-evident, structured audit trails tracking all system events, authentication attempts, and data operations.

---

## Architecture

```
User / Client → Frontend (React 19 + Vite + TypeScript + Tailwind CSS 4)
                   ↕ REST API (JWT Auth + RBAC + Tenant Isolation)
                 Backend (FastAPI + Python 3.10+)
                   ├── OCR Engine (PaddleOCR PP-OCRv4)
                   ├── Extraction Engine (Regex / Pattern Matching)
                   ├── Compliance Engine (Legal Metrology PCR Rules)
                   ├── Officer Review & Verification State Machine
                   ├── Enforcement Case Docket Service
                   └── SQLite Relational Database (AIOSqlite)
```

- **Frontend**: A modern, reactive single-page application built with React 19, Vite, TypeScript, and Tailwind CSS 4. Features image upload, bounding-box visualization, interactive SVG score gauges, multi-role workspaces, and 11 UI locales.
- **REST API**: Asynchronous FastAPI backend providing high-throughput endpoints for image upload, synchronous/asynchronous analysis, officer reviews, enforcement cases, and administrative governance.
- **OCR Engine**: PaddleOCR (PP-OCRv4) deep learning text detection (DBNet) & recognition (SVTR) with bounding-box coordinate tracking and angle classification.
- **Extraction Engine**: Hybrid extraction system using rule-based regular expressions and structured pattern matching.
- **Compliance Engine**: Declarative rule validation matrix implementing provisions of the Legal Metrology (Packaged Commodities) Rules.
- **SQLite Database**: Lightweight, local relational storage for inspection history, audit metadata, review snapshots, enforcement dockets, and score tracking.

---

## Technology Stack

| Layer / Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS 4 | Single-page application, responsive multi-role layout, high-performance styling, type safety |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, Pydantic | High-performance asynchronous REST API framework |
| **OCR Engine** | PaddleOCR (`paddleocr`, `paddlepaddle`), Pillow | Deep learning text detection (DBNet), recognition (SVTR), angle classification, and coordinate mapping |
| **Database** | SQLite, aiosqlite | Lightweight persistence for audits, reviews, enforcement dockets, and history |
| **Security & Auth** | JWT Tokens, bcrypt, Role-Based Access Control | Strict tenant and role isolation across 5 distinct user roles |
| **Localization** | i18next, React-i18next | 11 supported languages (English + 10 Indic languages) |
| **Charts & Visuals** | Native SVG & Tailwind Visualizations, Lucide React | Lightweight vector compliance score gauges, status distributions, progress indicators, and UI icons |

---

## Project Status & Verification

MetrCheck AI is a verified, fully functional prototype:

- **Backend Test Suite**: **1,040 passed tests** (0 failed, 3 warnings) covering unit, integration, RBAC, tenant isolation, compliance rules, and state machine workflows.
- **Frontend Production Build**: **0 TypeScript/build errors**, fully compiled Vite bundle.
- **Security & Authorization**: Authoritative backend RBAC and multi-tenant isolation across all endpoints.
- **Localization**: UI localization and report generation available in **10 Indic languages** (Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia) plus English.
- **Database Integrity**: Verified SQLite database with foreign-key constraints and zero corruption.

---

## Quick Start

### Prerequisites
- **Python 3.10+ / 3.11** (Python 3.11 recommended for PaddleOCR)
- **Node.js 18+** & **npm**

---

### Windows Automated Workflow (Recommended)

MetrCheck AI includes automated root scripts for effortless local setup, verification, and execution on Windows:

#### 1. Setup Dependencies (First-Time Initialization)
Run `setup.bat` from Command Prompt or PowerShell:
```powershell
.\setup.bat
```
This script provisions the root Python virtual environment (`venv/`), installs all backend dependencies from `requirements.txt`, and installs frontend packages via `npm install`.

#### 2. Launch Application
Start both the FastAPI backend and React frontend with a single command:
```powershell
.\run.bat
```
This launches the process supervisor (`runner.py`), performs automated pre-flight checks, verifies port availability, polls health endpoints, outputs an ASCII QR code for instant mobile Wi-Fi testing, and opens the dashboard in your default browser.

#### 3. Stop Application
To gracefully terminate all running servers:
```powershell
.\stop.bat
```
*(Or press `Ctrl+C` in the running `run.bat` terminal window).*

---

### Manual Startup (Cross-Platform / Custom)

If running on Linux, macOS, or in separate terminal sessions:

#### Step 1: Backend Setup
```bash
# From project root
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI backend
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Step 2: Frontend Setup
```bash
# In a new terminal, from project root
cd frontend
npm install
npm run dev
```

---

### Access Endpoints

- **Frontend Application**: [http://localhost:5173](http://localhost:5173)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check Endpoint**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## Demo Mode

For rapid evaluation and demonstration during hackathons and reviews, MetrCheck AI includes a zero-dependency **Demo Mode**. You can trigger pre-analyzed test cases directly from the dashboard:

| Case | Scenario | Expected Score | Details |
| :--- | :--- | :---: | :--- |
| **Case 1: Compliant** | Fully compliant packaged food label | **100 / 100** | All mandatory declarations present: MRP (incl. of all taxes), standard metric net weight (`500 g`), manufacturing date, manufacturer details with PIN code, customer helpline & email, Country of Origin (India). |
| **Case 2: Warning** | Minor formatting defect | **75 / 100** | Declarations are present, but uses non-standard metric abbreviation (`gms` instead of `g`) or missing dedicated consumer email while retaining telephone contact. |
| **Case 3: Violation** | Non-compliant packaging label | **35 / 100** | Critical omissions: Missing MRP declaration, missing consumer care contact info, and ambiguous manufacturer address without state or PIN code. |

To use Demo Mode:
1. Open the web interface at [http://localhost:5173](http://localhost:5173).
2. Click on **Demo Mode** in the sidebar or upload section.
3. Select **Compliant**, **Warning**, or **Violation** to review instant scoring, bounding-box highlights, and workflow transitions.

---

## API Endpoints

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Check API status, database connectivity, and OCR engine status |
| `POST` | `/api/analyze` | Upload a product label image for OCR processing and compliance analysis |
| `GET` | `/api/demo/{case_id}` | Retrieve mock analysis data for demo cases (`compliant`, `warning`, `violation`) |
| `GET` | `/api/history` | List all historical compliance analysis records |
| `GET` | `/api/history/{id}` | Retrieve full details of a specific inspection record |
| `GET` | `/api/report/{id}/download` | Download structured inspection audit report |
| `GET` | `/api/rules` | Fetch active Legal Metrology rules and validation parameters |
| `GET` | `/api/reviews` | List officer review records in the review queue |
| `POST` | `/api/reviews/{id}/verify` | Submit human verification verdict with field corrections |
| `GET` | `/api/enforcement/cases` | List escalated enforcement cases |
| `POST` | `/api/enforcement/cases` | Create or update statutory enforcement cases |
| `GET` | `/api/admin/users` | List users for administrative provisioning and lifecycle control |

---

## Documentation

Technical documentation, feature matrices, and architecture guides are organized in the [`docs/`](docs/) directory:

### Architecture Diagrams & Guides
| Document | Topic | Description |
| :--- | :--- | :--- |
| [**Architecture & Code Flow (PDF)**](docs/architecture/MetrCheck_AI_Complete_Architecture_and_Code_Flow.pdf) | Architecture | Complete system component dataflow, OCR pipeline, and rule evaluation architecture |
| [**Architecture & Connectivity (PDF)**](docs/architecture/MetrCheck_AI_Complete_Architecture_and_Connectivity_Guide.pdf) | Connectivity | Service topology, network configuration, and external integration connectivity |
| [**Complete Documentation (PDF)**](docs/architecture/MetrCheck_AI_Complete_Documentation.pdf) | Overview | Full unified prototype documentation and technical specifications |
| [**Interactive Operational Guide (HTML)**](docs/interactive_guide.html) | User Manual | Offline-capable interactive operational user guide and demonstration manual |

### Feature Matrices & Implementation Specifications
| Document | Focus Area | Description |
| :--- | :--- | :--- |
| [**Section 4: Extraction Engine**](docs/SECTION_4_EXTRACTION_FEATURE_MATRIX.md) | Information Extraction | Text extraction, field pattern matching, and normalization ([Report](docs/SECTION_4_EXTRACTION_IMPLEMENTATION_REPORT.md)) |
| [**Section 5: Evidence Locator**](docs/SECTION_5_EVIDENCE_FEATURE_MATRIX.md) | Evidence & Spatial UI | Bounding box spatial analysis, visual coordinate mapping, and evidence overlays ([Report](docs/SECTION_5_EVIDENCE_IMPLEMENTATION_REPORT.md)) |
| [**Section 6: Compliance Rules**](docs/SECTION_6_COMPLIANCE_FEATURE_MATRIX.md) | Statutory Rules | Codified Legal Metrology (Packaged Commodities) Rules, 2011 ([Report](docs/SECTION_6_COMPLIANCE_IMPLEMENTATION_REPORT.md)) |
| [**Section 7: Scoring & Risk**](docs/SECTION_7_SCORING_RISK_FEATURE_MATRIX.md) | Scoring Engine | Weighted scoring algorithm, risk indicators, and penalty rules ([Report](docs/SECTION_7_SCORING_RISK_IMPLEMENTATION_REPORT.md)) |
| [**Section 8: Pre-Print Compliance**](docs/SECTION_8_PREPRINT_FEATURE_MATRIX.md) | Merchant Pre-Print | Pre-print label verification, packaging artwork inspection, and proofing ([Report](docs/SECTION_8_PREPRINT_IMPLEMENTATION_REPORT.md)) |
| [**Section 9: Version Comparison**](docs/SECTION_9_VERSION_COMPARISON_FEATURE_MATRIX.md) | Versioning | Packaging revision diffing, change tracking, and artwork iteration timelines ([Report](docs/SECTION_9_VERSION_COMPARISON_IMPLEMENTATION_REPORT.md)) |
| [**Section 10: Human Verification**](docs/SECTION_10_HUMAN_VERIFICATION_FEATURE_MATRIX.md) | Officer Review | Human-in-the-loop review state machine, officer overrides, and audit trails ([Report](docs/SECTION_10_HUMAN_VERIFICATION_IMPLEMENTATION_REPORT.md)) |
| [**Section 13: External Verification**](docs/SECTION_13_EXTERNAL_VERIFICATION_AUDIT_REPORT.md) | External Integrations | FSSAI FoSCoS and GS1 GTIN verification architecture and validation rules |
| [**Section 15: Security & Integrity**](docs/SECTION_15_SECURITY_INTEGRITY_AUDIT_REPORT.md) | Security & Auditing | Multi-tenant isolation, role-based access control (RBAC), and tamper-evident logs |
| [**Section 16: Advanced Reporting**](docs/SECTION_16_ADVANCED_REPORTING_AUDIT_REPORT.md) | Reports & Exports | Multilingual ReportLab PDF generation across 10 Indic languages and Excel exports |
| [**Section 17: UX & Accessibility**](docs/SECTION_17_UX_ACCESSIBILITY_AUDIT_REPORT.md) | Accessibility | Design system, responsive layout, keyboard navigation, and high-contrast UI audit |
| [**Demo Runbook**](docs/reports/PHASE_5_SIH_DEMO_RUNBOOK.md) | Demonstration | Live evaluation runbook, demo cases, and failover workflows |

---

## Project Structure

```
Legal Metrology Compliance AI Prototype/
├── .env.example                     # Environment configuration template
├── .gitignore                       # Git ignore rules (includes .agents/, .runner.pid)
├── README.md                        # Project documentation and quickstart guide
├── run.bat                          # Windows one-command startup launcher
├── runner.py                        # Unified process supervisor and health check monitor
├── setup.bat                        # Windows one-command environment & dependency setup
├── stop.bat                         # Windows one-command graceful process shutdown
├── tunnel.bat                       # Local tunnel helper (cloudflared/ngrok) for mobile testing
├── allow_firewall.bat               # Windows firewall helper for ports 8000 & 5173
├── requirements.txt                 # Pinned root Python dependencies for local virtualenv
├── Dockerfile                       # Multi-stage production container build (FastAPI + Nginx)
├── docker-compose.yml               # Multi-service container orchestration
├── test_data/                       # Sample test packaging images for evaluation
│   ├── compliant/                   # Fully compliant packaging labels
│   ├── warning/                     # Labels with minor or formatting warnings
│   └── violation/                   # Labels with legal violations and omissions
├── doc_assets/                      # Diagram and screenshot assets referenced in documentation
├── docs/                            # Modular technical specifications & audit reports
│   ├── architecture/                # System, OCR, and compliance architecture PDFs
│   ├── interactive_guide.html       # Offline-capable interactive operational user guide
│   ├── reports/                     # Preserved historical audit and test execution reports
│   └── SECTION_*_FEATURE_MATRIX.md  # Modular section feature matrices & implementation reports
├── backend/                         # FastAPI Python backend
│   ├── api/                         # REST API route endpoints
│   ├── compliance/                  # Rule evaluation & scoring engine
│   ├── database/                    # SQLite database schema, connections, and migrations
│   ├── ocr/                         # PaddleOCR deep learning engine & preprocessing
│   ├── services/                    # Analysis, review, enforcement, and PDF/Excel services
│   ├── tests/                       # 1,040 passing pytest test suite
│   ├── main.py                      # FastAPI application entry point
│   └── requirements.txt             # Backend Python dependency manifest
└── frontend/                        # React 19 + TypeScript + Vite + Tailwind CSS frontend
    ├── src/
    │   ├── components/              # Layouts, workspaces, Evidence Viewer, and score gauges
    │   ├── context/                 # Auth, Workspace, and Language (i18n) contexts
    │   ├── i18n/locales/            # 11 supported language JSON translation dictionaries
    │   ├── pages/                   # Multi-role workspace dashboards & views
    │   ├── services/                # API client & backend bindings
    │   ├── types/                   # TypeScript interfaces & domain types
    │   └── App.tsx                  # Main router & role guards
    ├── package.json                 # Node dependencies and build scripts
    ├── vite.config.ts               # Vite build configuration
    └── Dockerfile                   # Standalone frontend production container definition
```

---

## Environment Variables

| Variable | Description | Default Value | Required |
| :--- | :--- | :--- | :---: |
| `OCR_ENGINE` | Optical Character Recognition backend (`paddleocr`) | `paddleocr` | No |
| `LLM_API_KEY` | Optional API key for LLM-assisted label parsing | *(empty)* | No |
| `UPLOAD_DIR` | Directory where uploaded product images are saved | `./uploads` | No |
| `DATABASE_PATH` | Path to SQLite database file | `./metrc_check.db` | No |
| `MAX_FILE_SIZE_MB` | Maximum allowed image file upload size in megabytes | `10` | No |
| `CORS_ORIGINS` | Comma-separated allowed HTTP origins for frontend CORS | `http://localhost:5173,http://localhost:3000` | No |
| `HOST` | Backend server network interface bind host | `0.0.0.0` | No |
| `PORT` | Backend server port number | `8000` | No |

---

## Disclaimer

> **Important Notice**  
> MetrCheck AI is an AI-assisted compliance prototype developed for Smart India Hackathon 2026 (Problem Statement: SIH26202). Compliance results and scores are indicative and designed to assist human inspectors and officers. This tool does not provide legally binding determinations or replace statutory regulatory authorities.

---

## License & Intellectual Property

No open-source license has been specified yet. All rights are reserved pending confirmation of the project's licensing and intellectual-property terms.
