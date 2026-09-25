# MetrCheck AI — Final Codebase Forensic Cleanup Audit

**Audit Execution Date:** 2026-09-24  
**Status:** PHASE 1 — READ-ONLY FORENSIC AUDIT COMPLETE  
**Mode:** READ-ONLY (No files deleted or moved yet)

---

## 1. Executive Summary

A comprehensive, non-destructive forensic audit of the entire MetrCheck AI repository was performed across all directories, modules, test suites, assets, scripts, configuration files, and documentation.

### Core Audit Findings
1. **Application Functionality & Workspaces**: All core workflows (Consumer, Merchant, Audit Officer, Enforcement Officer, Authentication, Officer Review, Enforcement Case Management, OCR/CV, Compliance Engine, Multilingual i18n, Tenant Isolation, RBAC) are fully verified, operational, and require zero code/logic modification.
2. **Database Integrity**: The primary database (`backend/metrc_check.db`) contains active seed and demo data across tenants. It must remain strictly preserved and untouched.
3. **Clutter Identification**:
   - 21 historical phase report markdown files are currently residing in the project root directory, creating visual clutter. These will be classified as **ARCHIVE** and moved into `docs/reports/`.
   - `frontend/src/archive/` contains 7 obsolete prototype UI components with 0 references across the entire codebase.
   - `scratch/` contains ephemeral debugging scripts and trace JSON files from previous investigations.
   - `backend/archive/ocr/` contains an empty folder, and `backend/archive/` has 3 legacy unreferenced scripts.
4. **Secret Safety**: No live secrets, passwords, or credentials are hardcoded in source files. Environment templates (`.env.example`, `backend/.env.example`) contain safe placeholders.

---

## 2. Comprehensive Inventory & File Classification

Every suspicious, temporary, legacy, and root file has been investigated for imports, runtime references, routes, and package/test requirements.

### Category Legend:
- **A. KEEP — ACTIVE PRODUCTION CODE**: Essential source code.
- **B. KEEP — REQUIRED CONFIGURATION**: Essential config and build files.
- **C. KEEP — TEST INFRASTRUCTURE**: Automated test suites and fixtures.
- **D. KEEP — DEMO / ASSET**: Production and demo images, documentation diagrams.
- **E. KEEP — DEPLOYMENT / DOCUMENTATION**: Core runbooks, setup, and deployment guides.
- **G. ARCHIVE — HISTORICAL DOCUMENTATION**: Phase audit reports to move to `docs/reports/`.
- **H. DELETE — CONFIRMED JUNK / OBSOLETE**: Unused legacy code with verified 0 references.
- **I. DELETE — GENERATED / TEMPORARY**: Scratch traces, caches, and ephemeral test dumps.
- **J. REVIEW REQUIRED — UNCERTAIN**: Files requiring explicit user confirmation before action.

---

### Section 1: Root-Level Files

| File / Path | Category | Reason & Dependency Evidence | Recommendation |
|---|---|---|---|
| `README.md` | **E. KEEP** | Authoritative system documentation & architecture guide. | KEEP in root |
| `DEMO_RUNBOOK.md` | **E. KEEP** | Official SIH live demonstration execution runbook. | KEEP in root |
| `DEPLOYMENT.md` | **E. KEEP** | Production and local deployment instructions. | KEEP in root |
| `requirements.txt` | **B. KEEP** | Root Python dependencies manifest. | KEEP in root |
| `Dockerfile` | **B. KEEP** | Production container build manifest. | KEEP in root |
| `docker-compose.yml` | **B. KEEP** | Multi-container local orchestration configuration. | KEEP in root |
| `.dockerignore` | **B. KEEP** | Docker build exclusion rules. | KEEP in root |
| `.gitignore` | **B. KEEP** | Git ignore rules (minor typo cleanup on line 68 needed). | KEEP in root |
| `.env.example` | **B. KEEP** | Root template for environment variables with safe defaults. | KEEP in root |
| `run.bat` | **B. KEEP** | Windows automated startup script for both servers. | KEEP in root |
| `setup.bat` | **B. KEEP** | Windows automated setup & environment initialization script. | KEEP in root |
| `stop.bat` | **B. KEEP** | Windows process termination utility. | KEEP in root |
| `tunnel.bat` | **B. KEEP** | Cloudflare tunnel helper for mobile/remote testing. | KEEP in root |
| `allow_firewall.bat` | **B. KEEP** | Windows firewall configuration utility for local network tests. | KEEP in root |
| `runner.py` | **A. KEEP** | Unified development runner executing backend & frontend. | KEEP in root |
| `PHASE_A01_3_AUDIT_ANALYSIS_OFFICER_REVIEW_INTEGRATION_REPORT.md` | **G. ARCHIVE** | Phase A-01.3 forensic integration audit report. | Move to `docs/reports/` |
| `PHASE_A02_OFFICER_REVIEW_HUMAN_VERIFICATION_FORENSIC_AUDIT.md` | **G. ARCHIVE** | Phase A-02 forensic audit report. | Move to `docs/reports/` |
| `PHASE_FINAL_2_CLEANUP_EXECUTION_REPORT.md` | **G. ARCHIVE** | Historical Phase 2 cleanup report. | Move to `docs/reports/` |
| `PHASE_FINAL_4_CONTROLLED_REMEDIATION_REPORT.md` | **G. ARCHIVE** | Historical Phase 4 remediation report. | Move to `docs/reports/` |
| `PHASE_FINAL_4_REMEDIATION_TEST_MATRIX.md` | **G. ARCHIVE** | Historical Phase 4 test matrix. | Move to `docs/reports/` |
| `PHASE_FINAL_5_1_PASSWORD_RESET_SECURITY_REMEDIATION_REPORT.md` | **G. ARCHIVE** | Historical Phase 5.1 password security report. | Move to `docs/reports/` |
| `PHASE_FINAL_5_RELEASE_CANDIDATE_MATRIX.md` | **G. ARCHIVE** | Historical Release Candidate test matrix. | Move to `docs/reports/` |
| `PHASE_FINAL_5_RELEASE_CANDIDATE_VERIFICATION_REPORT.md` | **G. ARCHIVE** | Historical Release Candidate verification report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_03_NORMAL_USER_DASHBOARD_FINALIZATION_REPORT.md` | **G. ARCHIVE** | Historical consumer dashboard finalization report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_04A_1_TARGETED_VERIFICATION_REPORT.md` | **G. ARCHIVE** | Historical verification report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_04A_2_MRP_FORENSIC_FIX_REPORT.md` | **G. ARCHIVE** | Historical MRP calculation forensic fix report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_04A_3_EVIDENCE_VIEWER_FIX_REPORT.md` | **G. ARCHIVE** | Historical evidence viewer fix report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_04A_ANALYSIS_RESULTS_CRITICAL_FIXES_REPORT.md` | **G. ARCHIVE** | Historical analysis results report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_04B_NORMAL_USER_COMPLETE_FUNCTIONALIZATION_REPORT.md` | **G. ARCHIVE** | Historical Consumer workspace report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_05A_ANALYSIS_SEMANTICS_AND_ID_FORENSIC_REPORT.md` | **G. ARCHIVE** | Historical analysis semantics report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_05B_PDF_REPORT_REDESIGN_AND_INFORMATION_QUALITY_REPORT.md` | **G. ARCHIVE** | Historical PDF report redesign report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_06_1_HOTFIX_MANUAL_CHECK_RBAC_REPORT.md` | **G. ARCHIVE** | Historical manual check hotfix report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_06_1_MANUAL_SAMPLE_PACKAGE_LOADER_REPORT.md` | **G. ARCHIVE** | Historical package loader report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_06_SIMPLE_CONSUMER_MANUAL_PRODUCT_CHECK_REPORT.md` | **G. ARCHIVE** | Historical consumer check report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_07_1_TRUE_MULTILINGUAL_RESULTS_AND_PDF_REPORT.md` | **G. ARCHIVE** | Historical multilingual PDF report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_CHECK_PRODUCT_LISTING_TEXT_REMOVAL_AND_LOCALIZATION_REPORT.md` | **G. ARCHIVE** | Historical listing text localization report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_LANGUAGE_FORENSIC_REMEDIATION_REPORT.md` | **G. ARCHIVE** | Historical language remediation report. | Move to `docs/reports/` |
| `PHASE_FINAL_NU_LANGUAGE_FORENSIC_VERIFICATION_REPORT.md` | **G. ARCHIVE** | Historical language verification report. | Move to `docs/reports/` |

---

### Section 2: Backend Files & Directories (`backend/`)

| File / Path | Category | Reason & Dependency Evidence | Recommendation |
|---|---|---|---|
| `backend/main.py` | **A. KEEP** | FastAPI entry point and route registration. | KEEP |
| `backend/config.py` | **A. KEEP** | Core application configuration & environment parser. | KEEP |
| `backend/version.py` | **A. KEEP** | Authoritative version manifest for system & rulesets. | KEEP |
| `backend/testing_utils.py` | **C. KEEP** | Isolated test environment context manager (`isolated_test_env`). | KEEP |
| `backend/requirements.txt` | **B. KEEP** | Backend Python package requirements. | KEEP |
| `backend/.env.example` | **B. KEEP** | Backend environment template. | KEEP |
| `backend/metrc_check.db` | **A. KEEP** | Active SQLite database with production/demo records. | **STRICTLY PRESERVE** |
| `backend/uploads/` | **D. KEEP** | Uploaded packaging artwork, product images, and thumbnails. | **PRESERVE** |
| `backend/api/` | **A. KEEP** | 10 API route controllers (analyses, reviews, enforcement, etc.). | KEEP |
| `backend/auth/` | **A. KEEP** | JWT auth, password hashing, RBAC, rate limiting. | KEEP |
| `backend/compliance/` | **A. KEEP** | Rule engine, evidence locator, scoring, recommendations. | KEEP |
| `backend/database/` | **A. KEEP** | Database layer, schema definitions, and entity CRUD helpers. | KEEP |
| `backend/extraction/` | **A. KEEP** | Metadata extraction engine and pattern matchers. | KEEP |
| `backend/integrations/` | **A. KEEP** | GS1 and FSSAI cross-verification providers and schemas. | KEEP |
| `backend/models/` | **A. KEEP** | Pydantic data contracts and schemas. | KEEP |
| `backend/multilingual/` | **A. KEEP** | 10-language translation registry, normalizer, and detector. | KEEP |
| `backend/ocr/` | **A. KEEP** | PaddleOCR engine, text cleaner, and repair helpers. | KEEP |
| `backend/services/` | **A. KEEP** | Core business logic services (analysis, review, reports, etc.). | KEEP |
| `backend/utils/` | **A. KEEP** | Datetime utils, backup_db, and input validators. | KEEP |
| `backend/vision/` | **A. KEEP** | Computer vision pipeline, region & barcode detectors. | KEEP |
| `backend/tests/` | **C. KEEP** | 50+ pytest test suites protecting all security and workflow invariants. | KEEP |
| `backend/archive/ocr/` | **H. DELETE** | Empty directory from legacy OCR experimentation. | DELETE |
| `backend/archive/ocr_preprocessing.py` | **H. DELETE** | Unused image preprocessing script with 0 imports. | DELETE |
| `backend/archive/ocr_regions.py` | **H. DELETE** | Unused region cropping script with 0 imports. | DELETE |
| `backend/archive/legacy_rules.py` | **H. DELETE** | Deprecated rules file replaced by `backend/compliance/rules/`. | DELETE |
| `backend/archive/db_backups/` | **B. KEEP** | 3 timestamped database backups created during schema migrations. | KEEP |

---

### Section 3: Frontend Files & Directories (`frontend/`)

| File / Path | Category | Reason & Dependency Evidence | Recommendation |
|---|---|---|---|
| `frontend/src/App.tsx` | **A. KEEP** | Master routing and workspace layout provider. | KEEP |
| `frontend/src/main.tsx` | **A. KEEP** | React application bootstrap entry. | KEEP |
| `frontend/src/index.css` | **A. KEEP** | Tailwind CSS base and utility directives. | KEEP |
| `frontend/src/pages/` | **A. KEEP** | 22 pages covering all Consumer, Merchant, Audit, Enforcement, Admin routes. | KEEP |
| `frontend/src/components/` | **A. KEEP** | 30+ interactive UI components (EvidenceViewer, Results, etc.). | KEEP |
| `frontend/src/context/` | **A. KEEP** | Auth, Workspace, Language, and Theme React contexts. | KEEP |
| `frontend/src/i18n/` | **A. KEEP** | 10 language translation files (en, hi, ta, te, mr, bn, gu, kn, ml, pa). | KEEP |
| `frontend/src/services/api.ts` | **A. KEEP** | Authoritative frontend API client. | KEEP |
| `frontend/src/types/` | **A. KEEP** | TypeScript interfaces and type definitions. | KEEP |
| `frontend/src/utils/` | **A. KEEP** | Date formatting and panel bounding box helpers (`panelHelper.ts`). | KEEP |
| `frontend/src/archive/components/Accordion.tsx` | **H. DELETE** | Obsolete legacy component (0 imports in project). | DELETE |
| `frontend/src/archive/components/CompactMetric.tsx` | **H. DELETE** | Obsolete legacy component (0 imports in project). | DELETE |
| `frontend/src/archive/components/ConfidenceBadge.tsx` | **H. DELETE** | Obsolete legacy component (0 imports in project). | DELETE |
| `frontend/src/archive/components/DataGrid.tsx` | **H. DELETE** | Obsolete legacy component (0 imports in project). | DELETE |
| `frontend/src/archive/components/FilterBar.tsx` | **H. DELETE** | Obsolete legacy component (0 imports in project). | DELETE |
| `frontend/src/archive/components/SectionHeader.tsx` | **H. DELETE** | Obsolete legacy component (0 imports in project). | DELETE |
| `frontend/src/archive/utils/classification.ts` | **H. DELETE** | Obsolete legacy utility (0 imports in project). | DELETE |

---

### Section 4: Scratch Directory (`scratch/`)

| File / Path | Category | Reason & Dependency Evidence | Recommendation |
|---|---|---|---|
| `scratch/analyze_pipeline_output.json` | **I. DELETE** | Ephemeral JSON dump from previous test run. | DELETE |
| `scratch/build_multilingual_locales.py` | **I. DELETE** | One-time locale generation scratch script (already completed). | DELETE |
| `scratch/inspect_jpeg_ocr.py` | **I. DELETE** | Temporary JPEG inspection script. | DELETE |
| `scratch/jpeg_ocr_text.txt` | **I. DELETE** | Temporary OCR output text file. | DELETE |
| `scratch/sync_sku_workflow.py` | **I. DELETE** | One-time SKU sync utility. | DELETE |
| `scratch/test_alpino_trace.py` | **I. DELETE** | Ad-hoc trace script (official tests reside in `backend/tests/`). | DELETE |
| `scratch/test_analyze_pipeline.py` | **I. DELETE** | Ad-hoc pipeline script (official tests reside in `backend/tests/`). | DELETE |
| `scratch/test_extractor_images.py` | **I. DELETE** | Ad-hoc extractor test script. | DELETE |
| `scratch/trace_output.json` | **I. DELETE** | Ad-hoc trace JSON dump. | DELETE |
| `scratch/update_analysis_locales.py` | **I. DELETE** | One-time locale update script. | DELETE |
| `scratch/__pycache__/` | **I. DELETE** | Python bytecode cache in scratch folder. | DELETE |

---

### Section 5: Scripts, Docs & Assets

| File / Path | Category | Reason & Dependency Evidence | Recommendation |
|---|---|---|---|
| `docs/architecture/` | **E. KEEP** | Architectural PDFs and connectivity specifications. | KEEP |
| `docs/reports/` | **G. ARCHIVE** | Directory storing historical phase and audit reports. | KEEP |
| `doc_assets/` | **D. KEEP** | 4 architecture and compliance flow diagrams referenced in docs. | KEEP |
| `scripts/generate_architecture_pdf.py` | **E. KEEP** | Architecture report PDF generation tool. | KEEP |
| `scripts/generate_diagrams.py` | **E. KEEP** | Architectural graph/diagram generator. | KEEP |
| `scripts/generate_more_diagrams.py`| **E. KEEP** | Secondary diagram generator. | KEEP |
| `test_data/ocr_bench/` | **C. KEEP** | Synthetic label images for OCR benchmark suite. | KEEP |
| `test_data/bench_ocr.py` | **C. KEEP** | Benchmark script for PaddleOCR performance evaluation. | KEEP |
| `test_data/e2e_smoke.py` | **J. REVIEW REQUIRED** | Manual smoke script with legacy hardcoded local path. | RETAIN (do not delete) |
| `.omp_tasks/` | **J. REVIEW REQUIRED** | Local task tracking notes. | RETAIN in gitignore |

---

## 3. Safe Deletion & Organization Plan (Pending Approval)

### Proposed Actions upon Approval:
1. **Archive Historical Reports**: Move 21 root-level `PHASE_*.md` files into `docs/reports/`.
2. **Remove Confirmed Junk in Frontend**: Remove unused `frontend/src/archive/` (7 files).
3. **Remove Confirmed Junk in Backend**: Remove `backend/archive/ocr/`, `ocr_preprocessing.py`, `ocr_regions.py`, and `legacy_rules.py`.
4. **Remove Scratch Artifacts**: Remove ephemeral files inside `scratch/`.
5. **Clean .gitignore Typo**: Remove accidental string `tatus --ignored` on line 68 of `.gitignore`.
6. **Zero Code Changes**: Zero changes to production Python modules, frontend TypeScript, routing, RBAC, or database records.

---

## 4. Verification Checkpoint

The read-only audit is complete. In accordance with execution instructions, **no files have been deleted or modified yet**.

Please review the audit classifications above. Upon your approval, the controlled cleanup will be executed and verified with the full automated test suite and frontend production build.
