# METRCHECK AI — FINALIZATION PHASE 1
# MASTER CODEBASE FORENSIC CLEANUP & ORGANIZATION AUDIT

**Document Type:** Master Codebase Forensic Cleanup & Repository Organization Audit  
**Phase:** Finalization Phase 1 (Post-Phase 5 Feature Complete Baseline)  
**Audit Date:** 2026-09-21  
**Audit Mode:** Strictly Read-Only (Zero Files Deleted, Zero Files Moved, Zero Code Mutated)  
**System Status:** Feature-Complete for SIH 2026 Prototype  
**Baseline Verification:** 877 Passed, 1 Skipped (PaddleOCR), 0 Failed | 0 TypeScript Errors  
**Final Audit Verdict:** `READY FOR CLEANUP IMPLEMENTATION`

---

## 1. EXECUTIVE SUMMARY

MetrCheck AI has completed all functional, security, isolation, and stability phases (Phases 1 through 5, including 4C.1 stabilization). The application is feature-complete for the SIH 2026 prototype.

This **Finalization Phase 1** audit is a comprehensive, read-only forensic examination of every file, module, script, database, asset, test suite, and configuration in the repository. The objective is to produce an authoritative inventory and safe cleanup roadmap prior to final packaging.

### Key Audit Findings:
1. **Accidental Shell Output in Root:** An accidental file named `tatus --ignored` (79 kB) exists in the repository root, generated from a typoed git command. **(SAFE TO DELETE)**
2. **Obsolete Root Database:** An old 12 KB `metrc_check.db` file resides in the root directory, while the actual runtime database is `backend/metrc_check.db` (6.5 MB). **(SAFE TO DELETE)**
3. **Database Backup Clutter:** Three historical `.db.backup` files totaling over 6.5 MB reside inside `backend/`. **(SAFE TO ARCHIVE)**
4. **Dead / Legacy Backend Code:**
   - `backend/compliance/rules.py` (legacy 10-rule prototype file superseded by `backend/compliance/rules/` package). **(SAFE TO ARCHIVE)**
   - `backend/ocr/preprocessing.py` (252 lines, `ImagePreprocessor` class unreferenced in production pipeline). **(SAFE TO ARCHIVE)**
   - `backend/ocr/regions.py` (132 lines, `LabelRegionDetector` class unreferenced in production pipeline). **(SAFE TO ARCHIVE)**
5. **Unused Frontend UI Components:** 7 unreferenced UI components and helper utilities in `frontend/src/components/ui/` (`Accordion.tsx`, `CompactMetric.tsx`, `ConfidenceBadge.tsx`, `DataGrid.tsx`, `FilterBar.tsx`, `SectionHeader.tsx`) and `frontend/src/utils/classification.ts`. **(SAFE TO ARCHIVE)**
6. **Git Hygiene & .gitignore Redundancies:** `.gitignore` contains duplicated blocks (lines 1–38 repeated in lines 39–85).
7. **Production Core Integrity:** All 99 database functions in `backend/database/db.py`, all 74 API endpoints across 20 routers, and all 14 statutory compliance rules in `backend/compliance/rules/` are verified as actively functional or required for backward compatibility and testing.

---

## 2. REPOSITORY ROOT INVENTORY

| Item Name | Type | Size | Category | Forensic Finding & Purpose | Recommended Action |
|---|---|---|---|---|---|
| `backend/` | Directory | — | A. REQUIRED SOURCE | Complete FastAPI backend, OCR engine, rule engine, auth, db | KEEP — REQUIRED |
| `frontend/` | Directory | — | A. REQUIRED SOURCE | React 19 + Vite + Tailwind frontend application | KEEP — REQUIRED |
| `docs/` | Directory | 148 kB | C. REQUIRED DOCUMENTATION | 18 Milestone reports and feature matrices (Sec 4–17) | KEEP — REQUIRED |
| `doc_assets/` | Directory | <1 kB | C. REQUIRED DOCUMENTATION | Architecture & pipeline diagrams | KEEP — REQUIRED |
| `test_data/` | Directory | — | D. REQUIRED TEST | Real/synthetic packaging test specimens & benchmark scripts | KEEP — REQUIRED |
| `Dockerfile` | File | 2.2 kB | E. REQUIRED DEPLOYMENT | Container build definition for MetrCheck AI | KEEP — REQUIRED |
| `docker-compose.yml` | File | 1.3 kB | E. REQUIRED DEPLOYMENT | Multi-service local/production container orchestration | KEEP — REQUIRED |
| `.env.example` | File | 1.0 kB | B. REQUIRED CONFIG | Environment template for secrets and URLs | KEEP — REQUIRED |
| `.gitignore` | File | 942 B | B. REQUIRED CONFIG | Git exclusion rules (contains duplicate blocks) | KEEP — CLEANUP DUPES |
| `.dockerignore` | File | 433 B | B. REQUIRED CONFIG | Container build ignore rules | KEEP — REQUIRED |
| `requirements.txt` | File | 1.2 kB | B. REQUIRED CONFIG | Root Python dependency manifest (with Python 3.11 notes) | KEEP — REQUIRED |
| `README.md` | File | 17.2 kB | C. REQUIRED DOCUMENTATION | Primary system documentation and architecture guide | KEEP — REQUIRED |
| `DEMO_RUNBOOK.md` | File | 14.5 kB | C. REQUIRED DOCUMENTATION | Step-by-step evaluator presentation guide | KEEP — REQUIRED |
| `DEPLOYMENT.md` | File | 5.1 kB | C. REQUIRED DOCUMENTATION | Production and container deployment runbook | KEEP — REQUIRED |
| `run.bat`, `setup.bat`, `stop.bat` | Scripts | ~2.6 kB | F. DEV TOOLING | Windows launch, setup, and teardown scripts | KEEP — DEV TOOLING |
| `allow_firewall.bat`, `tunnel.bat` | Scripts | ~1.6 kB | F. DEV TOOLING | Port forwarding and firewall management | KEEP — DEV TOOLING |
| `runner.py` | Script | 6.9 kB | F. DEV TOOLING | Unified multi-process runner for backend + frontend | KEEP — DEV TOOLING |
| `generate_architecture_pdf.py` | Script | 52.1 kB | F. DEV TOOLING | ReportLab script generating complete PDF architecture docs | KEEP — DEV TOOLING |
| `generate_diagrams.py`, `generate_more_diagrams.py` | Scripts | ~20 kB | F. DEV TOOLING | Graphviz/Pillow diagram generators for documentation | KEEP — DEV TOOLING |
| `interactive_guide.html` | File | 28.2 kB | C. DOCUMENTATION | Standalone HTML evaluator walkthrough | KEEP — DOCUMENTATION |
| `MetrCheck_AI_Complete_*.pdf` (3 files) | Artifacts | ~821 kB | C. DOCUMENTATION | Pre-generated architecture & connectivity PDFs | KEEP / ARCHIVE TO `docs/` |
| `PHASE_*_REPORT.md` (9 files) | Reports | ~180 kB | C. HISTORICAL REPORT | Phase 4, 4C, 4C.1, 5, 6.1 milestone verification reports | KEEP / MOVE TO `docs/reports/` |
| `tatus --ignored` | File | 79.1 kB | G. ACCIDENTAL ARTIFACT | Typo output from `git status --ignored` command | **SAFE TO DELETE** |
| `gh-device.json` | File | 165 B | H. TEMPORARY | GitHub CLI device authentication cache | **SAFE TO DELETE** |
| `metrc_check.db` (in root) | File | 12.3 kB | I. LEGACY DB | Stale root database (backend uses `backend/metrc_check.db`) | **SAFE TO DELETE** |
| `scratch/` | Directory | — | H. TEMPORARY | Temporary investigation scripts and json dumps | **SAFE TO DELETE** |
| `.omp_tasks/`, `.pytest_cache/`, `__pycache__/` | Dirs | — | H. CACHE | Local tooling execution caches | **IGNORE VIA GIT** |
| `venv/` | Directory | — | H. LOCAL RUNTIME | Local Python virtual environment | **IGNORE VIA GIT** |

---

## 3. BACKEND FORENSIC INVENTORY

### Directory Breakdown (116 Non-Test Python Files):

| Subsystem | Active Files | Dead / Obsolete Files | Purpose & State |
|---|---|---|---|
| `backend/api/` (20 files) | 20 active routers | 0 dead files | All routers included in `main.py` and serving endpoints |
| `backend/auth/` (3 files) | `routes.py`, `security.py`, `ratelimit.py` | 0 dead files | Complete authentication, RBAC, HMAC tokens, rate limiting |
| `backend/compliance/` (6 files + rules/) | `engine.py`, `evidence_locator.py`, `recommendations.py`, `scorer.py`, `rules/` (5 files) | `compliance/rules.py` (legacy prototype) | `compliance/rules.py` defines `DEMO_RULES` unreferenced by modular rule engine |
| `backend/database/` (1 file) | `db.py` (3791 lines) | 0 dead functions | 99 functions total: 93 production/API, 6 test/seeder helpers |
| `backend/enforcement/` (1 file) | `penalties.py` | 0 dead files | Section 36/38 statutory penalty calculator |
| `backend/extraction/` (3 files) | `extractor.py`, `patterns.py`, `llm_extractor.py` | 0 dead files | Deterministic regex & NER entity extractor |
| `backend/integrations/` (2 files + subdirs) | `cross_checker.py`, `fssai/`, `gs1/` | 0 dead files | FSSAI, GS1 DataKart, external cache verifiers |
| `backend/models/` (8 files) | 8 Pydantic schema files | 0 dead files | Request/response models for all subsystems |
| `backend/multilingual/` (6 files + dicts/) | 6 language modules | 0 dead files | 10 Indian script normalizers & dictionaries |
| `backend/ocr/` (8 files) | `paddle_engine.py`, `quality.py`, `repair.py`, `cleaner.py`, `factory.py`, `base.py` | `preprocessing.py`, `regions.py` | `ImagePreprocessor` and `LabelRegionDetector` are standalone uncalled classes |
| `backend/services/` (8 files) | 8 service modules | 0 dead files | Core business logic coordinators |
| `backend/scripts/` (3 files) | `bootstrap_admin.py`, `change_admin_credentials.py`, `cleanup_test_history.py` | 0 dead files | Standalone CLI management scripts |
| `backend/utils/` (3 files) | `datetime_utils.py`, `validators.py`, `backup_db.py` | 0 dead files | Shared helpers and backup utility |
| `backend/vision/` (15 files) | 15 CV modules | 0 dead files | Geometry, symbols, barcode, QR, quality detectors |

---

## 4. FRONTEND FORENSIC INVENTORY (73 Source Files)

### Component & Page Usage Matrix:

| Category | Total Files | Actively Imported & Routed | Unimported / Dead | Details |
|---|---|---|---|---|
| `pages/` | 26 files | 26 pages | 0 | All 26 pages mapped to routes in `App.tsx` |
| `components/layout/` | 3 files | 3 files (`Layout.tsx`, `Sidebar.tsx`, `ErrorBoundary.tsx`) | 0 | Root application layout and navigation |
| `components/results/` | 6 files | 6 files (`ComplianceSummary.tsx`, `EvidencePanel.tsx`, etc.) | 0 | Inspection report display widgets |
| `components/ui/` | 13 files | 7 files (`Badge.tsx`, `Button.tsx`, `Card.tsx`, `Modal.tsx`, `Spinner.tsx`, `Tabs.tsx`, `Toast.tsx`) | **6 files** | `Accordion.tsx`, `CompactMetric.tsx`, `ConfidenceBadge.tsx`, `DataGrid.tsx`, `FilterBar.tsx`, `SectionHeader.tsx` have 0 importers |
| `components/` (root) | 1 file | 1 file (`EvidenceViewer.tsx`) | 0 | Multi-panel bounding-box evidence inspection tool |
| `context/` | 4 files | 4 files (`AuthContext`, `RoleContext`, `ThemeContext`, `WorkspaceContext`) | 0 | Active state management |
| `services/` | 1 file | 1 file (`api.ts`) | 0 | Unified API client (78 called methods, 34 API utilities) |
| `utils/` | 2 files | 1 file (`cn.ts`) | **1 file** | `classification.ts` (0 importers in frontend; logic implemented in results) |
| `types/` | 1 file | 1 file (`index.ts`) | 0 | TypeScript interface definitions |

---

## 5. DATABASE CODE AUDIT

Detailed inspection of `backend/database/db.py` (3,791 lines, 99 functions):

### Breakdown of Function Categories:
- **Tenant & Organization DAO (8 functions):** `create_organization`, `get_organization`, `list_organizations`, `get_user_organization`, `set_user_organization`, etc. — **ALL ACTIVE**
- **Analysis Persistence DAO (10 functions):** `save_analysis`, `get_analysis`, `list_analyses`, `delete_analysis`, `count_analyses`, etc. — **ALL ACTIVE**
- **Product Catalog DAO (8 functions):** `save_product`, `get_product`, `list_products`, `delete_product`, `count_products_by_org`, etc. — **ALL ACTIVE**
- **Preprint Artwork DAO (7 functions):** `save_artwork`, `get_artwork`, `list_artworks`, `delete_artwork`, etc. — **ALL ACTIVE**
- **Version Comparison DAO (6 functions):** `save_version_comparison`, `get_version_comparison`, `list_version_comparisons`, etc. — **ALL ACTIVE**
- **Officer Review DAO (12 functions):** `save_review`, `get_review`, `list_reviews`, `assign_review`, `escalate_review`, etc. — **ALL ACTIVE**
- **Enforcement & Notices DAO (14 functions):** `save_enforcement_case`, `insert_enforcement_case`, `get_enforcement_case`, `list_enforcement_cases`, `save_enforcement_notice`, `list_penalties_by_case`, etc. — **ALL ACTIVE**
- **Security, Auth & Provisioning (18 functions):** `create_user`, `get_user_by_username`, `save_password_reset_token`, `save_download_ticket`, `redeem_download_ticket_in_db`, `append_security_audit_log`, `verify_security_audit_chain`, `record_rate_limit_event`, `create_officer_access_request`, etc. — **ALL ACTIVE**
- **Seeders & Test DAO (6 functions):** `seed_default_users`, `list_organizations`, `delete_review`, `delete_product`, `delete_cached_verification`, `classify_analysis_outcome` — **REQUIRED BY CONFTEST & DIRECT DAO TESTS**

**Conclusion:** `db.py` has **zero dead code**. Every function is either an active API dependency or an explicit test fixture dependency.

---

## 6. API ROUTER AUDIT (74 Operations)

| Category | Endpoint Count | Canonical vs Legacy | Status |
|---|---|---|---|
| **Analyze & Scan** | 2 endpoints | Canonical (`/api/analyze`, `/api/analyze/text`) | Active Production |
| **Compliance Rules** | 3 endpoints | Canonical (`/api/compliance/rules`, `/check`, `/test-rule`) | Active Production |
| **Evidence & Annotations** | 3 endpoints | Canonical (`/api/evidence/{id}`, `/audit/{id}`, `/modify`) | Active Production |
| **History & Stats** | 6 endpoints | Canonical (`/api/history`, `/history/{id}`, `/stats`, etc.) | Active Production |
| **Demo Packaging Cases** | 1 endpoint | Demo (`/api/demo/cases`) | Keep for Evaluator Demo |
| **System Health & Version** | 3 endpoints | Infrastructure (`/api/health`, `/api/version`, `/`) | Active Production |
| **Reports & Exports** | 5 endpoints | Canonical (`/api/report/{id}`, `/pdf`, `/csv`, `/xlsx`, `/json`) | Active Production |
| **Authentication & Profile** | 11 endpoints | Canonical + Legacy (`/auth/register` legacy; `/register-user`, `/register-merchant` canonical) | Keep Legacy for Compatibility |
| **Admin Governance** | 7 endpoints | Canonical (`/api/admin/users`, `/officer-requests/*`, `/security-logs/*`) | Active Production |
| **Enforcement Dockets** | 11 endpoints | Canonical + Legacy (`/enforcement/notice`, `/penalty` legacy; `/cases/{id}/...` canonical) | Keep Legacy for Compatibility |
| **Merchant Products** | 9 endpoints | Canonical (`/api/products/*`) | Active Production |
| **Preprint Artworks** | 6 endpoints | Canonical (`/api/preprint/*`) | Active Production |
| **Version Comparisons** | 7 endpoints | Canonical (`/api/versions/*`) | Active Production |
| **Audit Reviews** | 12 endpoints | Canonical (`/api/reviews/*`) | Active Production |
| **Integrations & Cache** | 7 endpoints | Canonical (`/api/integrations/*`) | Active Production |
| **Vision & Image Serving** | 2 endpoints | Canonical (`/api/vision/analyze`, `/api/images/{filename}`) | Active Production |

---

## 7. COMPLIANCE ENGINE AUDIT

- **Statutory Rules Registry:** Located in `backend/compliance/rules/`. Contains 14 active, versioned rules:
  - `LM-001`: Manufacturer / Packer / Importer Information
  - `LM-002`: Common / Generic Name of Commodity
  - `LM-003`: Net Quantity Declaration & Standard Unit
  - `LM-004`: Maximum Retail Price (MRP inclusive of all taxes)
  - `LM-005`: Consumer Care Details
  - `LM-006`: Country of Origin Declaration
  - `LM-007`: Unit Sale Price (USP) Declaration
  - `LM-008`: Date of Manufacture / Packing / Import
  - `LM-009`: Misleading Declarations & Pricing Integrity
  - `FS-001`: FSSAI Logo & 14-Digit Licence Number
  - `FS-002`: Name of Food
  - `FS-003`: List of Ingredients
  - `FS-004`: Nutritional Information Panel
  - `FS-005`: Date Marking (Best Before / Expiry / Use By)
- **Dead File Identified:** `backend/compliance/rules.py` (legacy 103-line prototype containing `DEMO_RULES`). It is not imported by `engine.py`, `registry.py`, or any API route.

---

## 8. OCR & COMPUTER VISION AUDIT

- **Active OCR Engine:** `backend/ocr/paddle_engine.py` (PaddleOCR PP-OCRv4) instantiated via `backend/ocr/factory.py` singleton.
- **Active Repair & Cleaning:** `backend/ocr/repair.py` and `backend/ocr/cleaner.py` (actively imported and tested).
- **Active Quality Assessment:** `backend/ocr/quality.py` (blur, exposure, glare detection).
- **Computer Vision Subsystem:** `backend/vision/` (15 modules for ArUco calibration, panel detection, symbols, veg/non-veg logos, barcodes, QR codes).
- **Dead OCR Modules Identified:**
  1. `backend/ocr/preprocessing.py`: Defines `ImagePreprocessor` with OpenCV Canny edge and contour perspective correction. It is not called by `paddle_engine.py` or `analysis_service.py`.
  2. `backend/ocr/regions.py`: Defines `LabelRegionDetector` with aspect-ratio heuristic bounding boxes. It is not called by the production pipeline.

---

## 9. INTEGRATION AUDIT

- **FSSAI / FoSCoS (`backend/integrations/fssai/`):** Full 14-digit structural validator, check-digit validation, state-code mapping, local SQLite `verification_cache`, and live `FoSCoSApiProvider` (unconfigured by default).
- **GS1 Barcode (`backend/integrations/gs1/`):** GS1 Modulo-10 Check Digit algorithm, GS1 country prefix table, local SQLite cache, and live `GS1DataKartProvider` (unconfigured by default).
- **Optical Calibration (`backend/services/calibration_service.py`):** ArUco marker mm-per-pixel calibration via OpenCV.
- **Email Delivery (`backend/auth/security.py`):** `SMTPDeliveryProvider` (production) and `DevLoggerDeliveryProvider` (development).
- **Rate Limiting (`backend/auth/ratelimit.py`):** Distributed sliding-window SQLite limiter.

---

## 10. AUTHENTICATION & SECURITY AUDIT

- **Hashing:** Standard-library PBKDF2-HMAC-SHA256 (200,000 iterations, 16-byte random salt).
- **Tokens:** Signed HMAC-SHA256 tokens with expiry and immediate `token_version` revocation.
- **RBAC:** 5 standardized roles: `ADMIN`, `ENFORCEMENT_OFFICER`, `AUDIT_OFFICER`, `MERCHANT_PUBLIC`, `PUBLIC_USER`.
- **Tenant Scoping:** `check_tenant_access()` fail-closed guard enforced across all data endpoints.
- **Audit Logs:** Immutable SHA-256 cryptographic chain in `security_audit_logs`.

---

## 11. TEST INVENTORY (67 Files, 878 Tests)

| Test Suite Category | File Count | Purpose | Execution Status |
|---|---|---|---|
| **Security & IDOR (SEC-01 to SEC-12)** | 12 files | Penetration testing for auth, tickets, rate limits, IDOR | 100% Passed |
| **Security Audit (SEC-AUD-01 to 07)** | 7 files | Tenant isolation, secret hardening, directory isolation | 100% Passed |
| **Phase Milestone Suites (Phase 2A to 4C.1)** | 11 files | Consumer, Merchant, Officer, Enforcement, Jurisdiction | 100% Passed |
| **Compliance & Scoring Intelligence** | 4 files | Statutory rules LM-001 to FS-005, weights, penalties | 100% Passed |
| **Extraction & Multilingual** | 10 files | 10 Indian scripts, NER, character repair, date extraction | 100% Passed |
| **Computer Vision & OCR Quality** | 7 files | ArUco, blur, exposure, symbols, barcodes, QR | 100% Passed |
| **Account Provisioning & Recovery (7.1–7.2)**| 5 files | Password reset, SMTP delivery, officer access approval | 100% Passed |
| **Real Packaging Benchmarks** | 3 files | Alpino Peanut Butter, Kissan Ketchup, Lays, TakaTak | 2 Passed, 1 Skipped (PaddleOCR) |
| **General Architecture & UX** | 8 files | History, Deletion, Admin UX, Preflight, Reporting | 100% Passed |

---

## 12. DOCUMENTATION INVENTORY

| Document Name | Location | Type | Status | Recommendation |
|---|---|---|---|---|
| `README.md` | Root | Primary Guide | CURRENT | KEEP in root |
| `DEMO_RUNBOOK.md` | Root | Evaluator Runbook | CURRENT | KEEP in root |
| `DEPLOYMENT.md` | Root | Ops Deployment Guide | CURRENT | KEEP in root |
| `PHASE_5_MASTER_FORENSIC_AUDIT.md` | Root | Phase 5 Audit | CURRENT | KEEP / MOVE to `docs/reports/` |
| `PHASE_4C_1_STABILIZATION_REPORT.md`| Root | Milestone Report | HISTORICAL | MOVE to `docs/reports/` |
| `PHASE_4C_SECURITY_INTEGRATION_REPORT.md`| Root | Milestone Report | HISTORICAL | MOVE to `docs/reports/` |
| `PHASE_4_PERFORMANCE_RELIABILITY_AUDIT_REPORT.md`| Root | Milestone Report | HISTORICAL | MOVE to `docs/reports/` |
| `PHASE_5_SIH_DEMO_RUNBOOK.md` | Root | Demo Runbook | HISTORICAL / DUP | MOVE to `docs/reports/` |
| `PHASE_5_SIH_DEMO_STRESS_TEST_REPORT.md`| Root | Milestone Report | HISTORICAL | MOVE to `docs/reports/` |
| `PHASE_6_1_*.md` (3 files) | Root | Milestone Reports | HISTORICAL | MOVE to `docs/reports/` |
| `PROJECT_FEATURE_BUG_GAP_AUDIT.md` | Root | Historical Audit | HISTORICAL | MOVE to `docs/reports/` |
| `SECTION_*.md` (18 files) | `docs/` | Milestone Specs | HISTORICAL | KEEP in `docs/` |
| `MetrCheck_AI_Complete_*.pdf` (3 files)| Root | PDF Architecture | COMPILED DOCS | MOVE to `docs/pdf/` |
| `interactive_guide.html` | Root | Standalone Guide | COMPILED DOCS | MOVE to `docs/` |

---

## 13. GENERATED ARTIFACT & CACHE INVENTORY

| Artifact / Cache Path | Location | Size | Type | Recommendation |
|---|---|---|---|---|
| `tatus --ignored` | Root | 79.1 kB | Typo Output File | **DELETE** |
| `gh-device.json` | Root | 165 B | Temporary Auth Token | **DELETE** |
| `metrc_check.db` | Root | 12.3 kB | Stale DB Copy | **DELETE** |
| `scratch/` | Root | ~150 kB | Dev Scratch Scripts | **DELETE / IGNORE** |
| `backend/metrc_check.db.backup_20260907_201535` | `backend/` | 2.1 MB | DB Backup | **ARCHIVE / IGNORE** |
| `backend/metrc_check_backup_before_targeted_cleanup_20260913_230452.db` | `backend/` | 2.3 MB | DB Backup | **ARCHIVE / IGNORE** |
| `backend/metrc_check_backup_before_user_cleanup.db` | `backend/` | 2.1 MB | DB Backup | **ARCHIVE / IGNORE** |
| `backend/metrcheck.db` | `backend/` | 0 B | Empty file | **DELETE** |
| `backend/uploads/` | `backend/` | Variable | Runtime User Uploads | **IGNORE VIA GIT** |
| `__pycache__/`, `.pytest_cache/` | Various | Variable | Python Bytecode Cache | **IGNORE VIA GIT** |
| `frontend/dist/` | `frontend/` | Variable | Vite Production Build | **IGNORE VIA GIT** |
| `frontend/node_modules/` | `frontend/` | Variable | Node Dependencies | **IGNORE VIA GIT** |
| `venv/`, `backend/venv/`, `backend/venv311/` | Various | Variable | Virtual Environments | **IGNORE VIA GIT** |

---

## 14. DEPENDENCY AUDIT

### Python Dependencies (`requirements.txt`):
- **FastAPI, Uvicorn, Python-Multipart, Starlette:** Core Web API — **REQUIRED**
- **Pillow, OpenCV-Python, NumPy:** Image decoding & CV analysis — **REQUIRED**
- **PaddleOCR, PaddlePaddle:** Deep learning OCR engine — **REQUIRED**
- **aiosqlite, aiofiles:** Async SQLite persistence and file handling — **REQUIRED**
- **Pydantic, Pydantic-Settings, Python-Dotenv:** Data schemas & environment config — **REQUIRED**
- **ReportLab, OpenPyXL, Jinja2, QRCode:** PDF, Excel, and templated exports — **REQUIRED**
- **HTTPX:** Async HTTP client for external registry lookups — **REQUIRED**
- **Pytest, Pytest-Asyncio:** Automated regression test framework — **REQUIRED**

### NPM Dependencies (`frontend/package.json`):
- **React, React-DOM (v19):** UI framework — **REQUIRED**
- **React-Router-DOM (v7):** Client-side routing — **REQUIRED**
- **Lucide-React:** UI icons across all 26 screens — **REQUIRED**
- **Recharts (v3):** Analytics charts on dashboards — **REQUIRED**
- **TailwindCSS, @tailwindcss/vite (v4):** Styling engine — **REQUIRED**
- **TypeScript, Vite, Oxlint:** Build and typing tools — **REQUIRED**

**Conclusion:** Zero unused third-party dependencies exist in either `requirements.txt` or `package.json`.

---

## 15. ENVIRONMENT & SECRET AUDIT

- **Template:** `.env.example` is complete and contains placeholder keys for:
  - `SECRET_KEY` (placeholder)
  - `ENVIRONMENT` (`development` / `production`)
  - `DATABASE_PATH`
  - `UPLOAD_DIR`
  - `CORS_ORIGINS`
  - `FSSAI_API_URL`, `FSSAI_API_KEY` (placeholder)
  - `GS1_API_URL`, `GS1_API_KEY` (placeholder)
  - `METRCHECK_SMTP_HOST`, `METRCHECK_SMTP_USER`, `METRCHECK_SMTP_PASS` (placeholder)
- **Security Check:** Zero real production API keys or passwords are committed to source control.
- **Startup Protection:** `config.py` contains `validate_production_secrets()` which halts startup in `production` mode if weak or default secrets are detected.

---

## 16. DUPLICATE CODE FINDINGS

1. **Rule Definitions:** `backend/compliance/rules.py` (legacy demo rules) duplicates concepts formalized in `backend/compliance/rules/legal_metrology.py` and `fssai.py`.
2. **Backward Compatible Routes:** `/api/auth/register` (legacy) vs `/api/auth/register-user` and `/api/auth/register-merchant` (canonical). Both are maintained intentionally for backward compatibility.
3. **Legacy Enforcement Endpoints:** `/api/enforcement/notice` and `/api/enforcement/penalty` exist alongside canonical `/api/enforcement/cases/{id}/notices` and `/cases/{id}/calculate-penalty`. Both are maintained intentionally.
4. **.gitignore Duplicate Blocks:** Lines 1–38 and 39–85 in root `.gitignore` contain redundant identical patterns.

---

## 17. DEAD CODE FINDINGS

| Item Path | Type | Why Unused | Risk of Removal | Recommended Action |
|---|---|---|---|---|
| `backend/compliance/rules.py` | Python Module | Legacy demo rule definitions superseded by modular `compliance/rules/` package. | None | **SAFE TO ARCHIVE** |
| `backend/ocr/preprocessing.py` | Python Module | `ImagePreprocessor` class unreferenced by production `PaddleOCREngine` or `analysis_service.py`. | None | **SAFE TO ARCHIVE** |
| `backend/ocr/regions.py` | Python Module | `LabelRegionDetector` class unreferenced by production pipeline. | None | **SAFE TO ARCHIVE** |
| `frontend/src/components/ui/Accordion.tsx` | TSX Component | Unimported in `frontend/src`. | None | **SAFE TO ARCHIVE** |
| `frontend/src/components/ui/CompactMetric.tsx` | TSX Component | Unimported in `frontend/src`. | None | **SAFE TO ARCHIVE** |
| `frontend/src/components/ui/ConfidenceBadge.tsx` | TSX Component | Unimported in `frontend/src`. | None | **SAFE TO ARCHIVE** |
| `frontend/src/components/ui/DataGrid.tsx` | TSX Component | Unimported in `frontend/src`. | None | **SAFE TO ARCHIVE** |
| `frontend/src/components/ui/FilterBar.tsx` | TSX Component | Unimported in `frontend/src`. | None | **SAFE TO ARCHIVE** |
| `frontend/src/components/ui/SectionHeader.tsx` | TSX Component | Unimported in `frontend/src`. | None | **SAFE TO ARCHIVE** |
| `frontend/src/utils/classification.ts` | TS Utility | Unimported in `frontend/src` (outcome logic inlined in components). | None | **SAFE TO ARCHIVE** |

---

## 18. MISPLACED FILE FINDINGS

1. **Root Directory Clutter:** 9 historical milestone markdown reports (`PHASE_*.md`), 3 compiled PDFs, and 3 Python diagram generation scripts currently clutter the root directory.
2. **Accidental Shell Output:** `tatus --ignored` in the root directory.
3. **Database in Root:** `metrc_check.db` in root (backend runtime uses `backend/metrc_check.db`).

---

## 19. GIT HYGIENE FINDINGS

1. **Untracked Files:** Ensure `.omp_tasks/`, `scratch/`, and temporary databases are added to `.gitignore`.
2. **Clean `.gitignore`:** Remove duplicate lines and organize into clear sections (Python, Node, Databases, Backups, Caches, Runtime Uploads).

---

## 20. PROPOSED FINAL REPOSITORY STRUCTURE

```
Legal Metrology Compliance AI Prototype/
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── README.md
├── DEMO_RUNBOOK.md
├── DEPLOYMENT.md
├── requirements.txt
│
├── backend/
│   ├── api/                     # 20 FastAPI Route Controllers
│   ├── auth/                    # RBAC, Security, Tokens, Rate Limiting
│   ├── compliance/              # Statutory Rule Engine
│   │   ├── rules/               # LM-001 to LM-009, FS-001 to FS-005
│   │   ├── engine.py
│   │   ├── evidence_locator.py
│   │   ├── recommendations.py
│   │   └── scorer.py
│   ├── database/
│   │   └── db.py                # 17 Relational Tables DAO
│   ├── enforcement/             # Section 36/38 Penalty Calculator
│   ├── extraction/              # Deterministic NER & Pattern Parser
│   ├── fixtures/                # Reference Packaging Images
│   ├── integrations/            # FSSAI FoSCoS & GS1 DataKart Connectors
│   ├── models/                  # Pydantic Schemas
│   ├── multilingual/            # 10 Indian Languages & Scripts
│   ├── ocr/                     # PP-OCRv4 Deep Learning Engine
│   ├── scripts/                 # Admin Bootstrap & CLI Utilities
│   ├── services/                # Business Logic Services
│   ├── templates/               # Report HTML Templates
│   ├── tests/                   # 67 Test Files (878 Test Cases)
│   ├── utils/                   # Datetime & Validation Utilities
│   ├── vision/                  # OpenCV Computer Vision Pipeline
│   ├── config.py
│   ├── main.py
│   └── version.py
│
├── frontend/
│   ├── src/
│   │   ├── components/          # Layout, Results, EvidenceViewer, UI
│   │   ├── context/             # Auth, Role, Theme, Workspace
│   │   ├── pages/               # 26 Screen Views across 5 Roles
│   │   ├── services/            # api.ts (Unified API Client)
│   │   ├── types/               # TypeScript Definitions
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── docs/
│   ├── architecture/            # Generated Architecture & Connectivity PDFs
│   ├── reports/                 # Historical Phase & Milestone Reports (Phase 4–6.1)
│   ├── sections/                # Section 4–17 Specification Reports
│   └── interactive_guide.html
│
├── scripts/                     # Dev, Build & Presentation Utility Scripts
│   ├── run.bat
│   ├── setup.bat
│   ├── stop.bat
│   ├── allow_firewall.bat
│   ├── tunnel.bat
│   ├── runner.py
│   ├── generate_architecture_pdf.py
│   ├── generate_diagrams.py
│   └── generate_more_diagrams.py
│
└── test_data/                   # Packaging Test Datasets & Benchmarks
```

---

## 21. FILES SAFE TO DELETE

| File Path | Size | Reason for Deletion |
|---|---|---|
| `tatus --ignored` | 79.1 kB | Accidental shell command typo output in root |
| `gh-device.json` | 165 B | Temporary GitHub device authentication token |
| `metrc_check.db` (in root) | 12.3 kB | Stale, inactive root database file |
| `backend/metrcheck.db` | 0 B | Empty, unused file |
| `scratch/` | ~150 kB | Temporary audit/investigation scripts |

---

## 22. FILES SAFE TO ARCHIVE

| Source Path | Proposed Archive Destination | Reason |
|---|---|---|
| `backend/compliance/rules.py` | `backend/archive/legacy_rules.py` | Legacy demo rules superseded by `compliance/rules/` |
| `backend/ocr/preprocessing.py` | `backend/archive/ocr_preprocessing.py` | Unused OpenCV perspective preprocessor |
| `backend/ocr/regions.py` | `backend/archive/ocr_regions.py` | Unused heuristic region detector |
| `frontend/src/components/ui/Accordion.tsx` | `frontend/src/archive/Accordion.tsx` | Unreferenced UI component |
| `frontend/src/components/ui/CompactMetric.tsx` | `frontend/src/archive/CompactMetric.tsx` | Unreferenced UI component |
| `frontend/src/components/ui/ConfidenceBadge.tsx` | `frontend/src/archive/ConfidenceBadge.tsx` | Unreferenced UI component |
| `frontend/src/components/ui/DataGrid.tsx` | `frontend/src/archive/DataGrid.tsx` | Unreferenced UI component |
| `frontend/src/components/ui/FilterBar.tsx` | `frontend/src/archive/FilterBar.tsx` | Unreferenced UI component |
| `frontend/src/components/ui/SectionHeader.tsx` | `frontend/src/archive/SectionHeader.tsx` | Unreferenced UI component |
| `frontend/src/utils/classification.ts` | `frontend/src/archive/classification.ts` | Unreferenced utility |
| `backend/metrc_check.db.backup_*` (3 files) | `backend/archive/db_backups/` | Historical local database snapshots |
| `PHASE_*_REPORT.md` (9 files in root) | `docs/reports/` | Milestone reports organized into documentation |
| `MetrCheck_AI_Complete_*.pdf` (3 files in root) | `docs/architecture/` | Compiled architecture documentation |

---

## 23. FILES TO KEEP FOR COMPATIBILITY

| File / Component | Purpose |
|---|---|
| `backend/api/auth/routes.py: /api/auth/register` | Preserved for legacy client backward compatibility |
| `backend/api/enforcement.py: /api/enforcement/notice` | Preserved for legacy notice generation scripts |
| `backend/api/enforcement.py: /api/enforcement/penalty` | Preserved for legacy penalty evaluation scripts |
| `backend/extraction/llm_extractor.py` | Preserved as unified wrapper interface for extractor calls |
| `frontend/src/services/api.ts` unused methods | Preserved for external API consumption & CLI tooling |

---

## 24. FILES TO KEEP FOR SIH DEMO

| File Path | Purpose |
|---|---|
| `DEMO_RUNBOOK.md` | Primary SIH evaluator demonstration script |
| `backend/api/demo.py` & `backend/demo/cases.py` | Provides pre-canned demo packaging cases (`demo-1`, `demo-2`, `demo-3`) |
| `backend/fixtures/` | Real packaging test images (Alpino, Lays, TakaTak) for live demonstration |
| `test_data/` | Synthetic test cases for bulk scanning and calibration demos |
| `interactive_guide.html` | Interactive offline presentation guide |

---

## 25. FILES REQUIRED FOR PRODUCTION

- All 20 API routers in `backend/api/`
- Full security layer in `backend/auth/`
- Modular statutory rule engine in `backend/compliance/rules/`
- DAO in `backend/database/db.py`
- Deep learning OCR engine in `backend/ocr/paddle_engine.py`
- All 26 page views in `frontend/src/pages/`
- Core UI components and `EvidenceViewer.tsx` in `frontend/src/components/`
- `Dockerfile` and `docker-compose.yml`

---

## 26. FILES REQUIRING MANUAL REVIEW

1. **Root Batch Scripts vs Root Python Scripts:** Review whether `.bat` scripts (`run.bat`, `setup.bat`) should remain in root or move to a `scripts/` folder with root wrapper shortcuts.
2. **Historical Milestone Reports in Root:** Confirm moving the 9 root `PHASE_*.md` files to `docs/reports/`.

---

## 27. RECOMMENDED CLEANUP EXECUTION ORDER (Next Phase)

```
Step 1: Delete accidental shell artifacts & stale root database
        - Delete 'tatus --ignored'
        - Delete 'gh-device.json'
        - Delete root 'metrc_check.db'
        - Delete 'backend/metrcheck.db'
        - Delete 'scratch/' directory

Step 2: Clean up .gitignore
        - Deduplicate redundant blocks in root .gitignore
        - Ensure .omp_tasks/, *.backup*, uploads/ are properly excluded

Step 3: Move documentation & PDF artifacts to docs/
        - Move root PHASE_*.md reports to docs/reports/
        - Move root MetrCheck_AI_Complete_*.pdf files to docs/architecture/
        - Move root interactive_guide.html to docs/

Step 4: Move development scripts to scripts/
        - Move root diagram/PDF generation scripts to scripts/

Step 5: Archive unreferenced dead code
        - Archive backend/compliance/rules.py
        - Archive backend/ocr/preprocessing.py and backend/ocr/regions.py
        - Archive unimported UI components in frontend/src/components/ui/

Step 6: Run verification pass
        - Run full pytest regression suite (target: 877 passed, 1 skipped, 0 failed)
        - Run frontend build (target: 0 TypeScript errors, clean build)
        - Run backend startup check (target: healthy 200 OK)
```

---

## 28. RISKS & MITIGATIONS

| Identified Risk | Severity | Mitigation Strategy |
|---|---|---|
| Accidental deletion of active code | HIGH | Strictly follow the inventory. Only delete confirmed accidental files (`tatus --ignored`, `gh-device.json`). All source code is archived, never deleted. |
| Breaking legacy test harnesses | MEDIUM | Retain all backward-compatible endpoints (`/api/auth/register`, `/api/enforcement/notice`). |
| Modifying database schema | HIGH | Zero database DDL or table changes during cleanup. |

---

## 29. FINAL CLEANUP PLAN MATRIX

| Step | Target Item | Action | Justification |
|---|---|---|---|
| **1.1** | `tatus --ignored` | DELETE | Accidental typo output file (79 kB) |
| **1.2** | `gh-device.json` | DELETE | Temporary auth token (165 B) |
| **1.3** | Root `metrc_check.db` | DELETE | Stale 12 KB file (active DB is in `backend/`) |
| **1.4** | `backend/metrcheck.db` | DELETE | Empty 0-byte file |
| **1.5** | `scratch/` | DELETE | Ephemeral audit scripts |
| **2.1** | Root `.gitignore` | REFACTOR | Deduplicate identical repeated blocks |
| **3.1** | Root `PHASE_*.md` files (9 files) | MOVE → `docs/reports/` | Organize root directory clutter |
| **3.2** | Root PDF files (3 files) | MOVE → `docs/architecture/`| Organize compiled documentation |
| **4.1** | Root `generate_*.py` (3 files) | MOVE → `scripts/` | Group tooling scripts together |
| **5.1** | `backend/compliance/rules.py` | ARCHIVE | Legacy prototype demo rules |
| **5.2** | `backend/ocr/preprocessing.py` | ARCHIVE | Unreferenced perspective preprocessor |
| **5.3** | `backend/ocr/regions.py` | ARCHIVE | Unreferenced region detector |
| **5.4** | 6 unimported UI components | ARCHIVE | Unreferenced prototype widgets |
| **6.1** | Test Suite & Build Verification | VERIFY | Run `pytest` (877 pass) and `npm run build` |

---

## 30. FINAL VERDICT

```
╔══════════════════════════════════════════════════════════════════════════════════════╗
║               METRCHECK AI — FINALIZATION PHASE 1 AUDIT VERDICT                      ║
║                                                                                      ║
║  FINAL VERDICT:                                                                      ║
║    ✅  READY FOR CLEANUP IMPLEMENTATION                                              ║
║                                                                                      ║
║  The repository forensic inventory is complete. All active production code, test    ║
║  suites, and documentation have been mapped. Zero breaking changes or refactoring    ║
║  are required. Cleanup can proceed safely according to the Step 1–6 execution plan.  ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
```
