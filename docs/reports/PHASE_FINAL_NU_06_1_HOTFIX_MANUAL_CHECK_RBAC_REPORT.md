# PHASE FINAL NU-06.1 HOTFIX — MANUAL PRODUCT CHECK RBAC FORENSIC & RESOLUTION REPORT

**Platform:** MetrCheck AI — Legal Metrology Compliance AI Platform  
**Target Workspace:** Normal User / Consumer Workspace (`PUBLIC_USER`)  
**Phase Completed:** NU-06.1 Hotfix — Runtime Authorization & Role Verification  
**Date:** September 2026  
**Status:** FULLY RESOLVED & VERIFIED  

---

## 1. Executive Summary

During runtime evaluation of the **Manual Product Check** workflow (`/manual-check`), an authorization boundary analysis was performed to verify how `POST /api/analyze/manual` evaluates caller roles, tokens, and privilege boundaries.

This investigation audited the exact role strings across backend authentication (`auth/security.py`), user models (`database/db.py`), route handlers (`api/analyze.py`), and frontend session context (`Sidebar.tsx`, `WorkspaceContext.tsx`, `AuthContext.tsx`).

The small, safe, non-breaking alignment was verified: `require_roles(ROLE_USER, "NORMAL_USER", "USER", ROLE_ADMIN)` ensures that all valid normal user representations (`PUBLIC_USER`, `NORMAL_USER`, `USER`) and administrators can access Manual Product Check, while non-consumer roles (`MERCHANT_PUBLIC`, `AUDIT_OFFICER`, `ENFORCEMENT_OFFICER`) and unauthenticated callers remain strictly rejected with 403 / 401.

---

## 2. Authorization Chain Forensic Audit

### 2.1 Complete Request Flow
```
ManualProductCheck.tsx
        ↓
frontend API client (api.analyzeManual -> fetchJSON)
        ↓  [Sends: Authorization: Bearer <token>]
POST /api/analyze/manual
        ↓
backend/api/analyze.py (analyze_manual_endpoint)
        ↓
FastAPI Depends(require_roles(ROLE_USER, "NORMAL_USER", "USER", ROLE_ADMIN))
        ↓
get_current_user (decodes HMAC token, fetches DB record, checks status & token_version)
        ↓
role guard (verifies user["role"] in allowed roles -> raises 403 "Insufficient privileges for this operation." if disallowed)
        ↓
services/analysis_service.py (analyze_manual)
        ↓
Authoritative Compliance Engine + Rule 12 Zero-Fabrication Tier ("NOT_ASSESSED")
        ↓
Result Persistence + History Ownership (owner_user_id)
```

### 2.2 Roles Matrix & Mappings

| Role Constant | Value | Manual Check Status | Rationale |
| :--- | :--- | :--- | :--- |
| `ROLE_USER` | `"PUBLIC_USER"` | **ALLOWED (200 OK)** | Canonical normal consumer user role |
| Alias | `"NORMAL_USER"` | **ALLOWED (200 OK)** | Compatibility alias for legacy/test public user tokens |
| Alias | `"USER"` | **ALLOWED (200 OK)** | Compatibility alias matching `org_type="USER"` & `security.py` line 660 |
| `ROLE_ADMIN` | `"ADMIN"` | **ALLOWED (200 OK)** | System administration & governance oversight |
| `ROLE_MERCHANT` | `"MERCHANT_PUBLIC"` | **DENIED (403 Forbidden)** | Commercial packagers must use Merchant Pre-Flight & Packaging Catalog |
| `ROLE_AUDIT` | `"AUDIT_OFFICER"` | **DENIED (403 Forbidden)** | Regulatory QA inspectors must use Official Review Workspace |
| `ROLE_ENFORCEMENT` | `"ENFORCEMENT_OFFICER"`| **DENIED (403 Forbidden)** | Statutory officials must use Enforcement Cases Workspace |
| Anonymous | `None` / Invalid Token | **DENIED (401 Unauthorized)** | Authentication is strictly mandatory |

---

## 3. Exact Root Cause & Resolution

1. **Role Alignment:** In `backend/api/analyze.py`, line 137 previously guarded the endpoint with:
   ```python
   user: dict = Depends(require_roles(ROLE_USER, "NORMAL_USER", ROLE_ADMIN))
   ```
   To align with `check_tenant_access` in `backend/auth/security.py` (line 660) and `database/db.py` (line 880/978), the alias `"USER"` was incorporated:
   ```python
   user: dict = Depends(require_roles(ROLE_USER, "NORMAL_USER", "USER", ROLE_ADMIN))
   ```
2. **Security Integrity Preserved:**
   - No open/anonymous access permitted.
   - Merchant (`MERCHANT_PUBLIC`) and Officer (`AUDIT_OFFICER`, `ENFORCEMENT_OFFICER`) roles are strictly forbidden (403 `Insufficient privileges for this operation.`).
   - Tenant isolation, rate limiting, and personal scan ownership remain 100% active.

---

## 4. Verification & Acceptance Results

### 4.1 Automated Test Verification
- **Target Suite (`test_nu06_consumer_manual_product_check.py`):** **16/16 passed (100%)**
  - `test_public_user_allowed` (200 OK)
  - `test_normal_user_and_user_alias_allowed` (200 OK for `NORMAL_USER` and `USER`)
  - `test_admin_allowed` (200 OK)
  - `test_unauthenticated_rejected` (401/403)
  - `test_merchant_rejected` (403 Forbidden with `"Insufficient privileges"`)
  - `test_officers_rejected` (403 Forbidden with `"Insufficient privileges"`)
  - `test_crunchkart_demo_sample_package_evaluation` (200 OK, Score 96.2, Rule 12 NOT_ASSESSED)
  - `test_pdf_stream_validity_and_manual_mode_markers` (200 OK)
  - `test_tenant_isolation_and_delete` (200 OK)
- **Frontend Production Build:** `npm --prefix frontend run build` — **Clean (0 errors, 0 warnings)**.

### 4.2 End-to-End Manual Workflow Execution
```
=== 1. Login as Normal User ===
Authenticated as: user | Role: PUBLIC_USER

=== 2. Submit CrunchKart Sample Package to Manual Check ===
Analysis ID generated: 525b302e-0f44-4c52-8f7d-af03f6ad23ec
Compliance Score: 96.2
Triage Status: REVIEW REQUIRED
Rule 12 Readability Tier: NOT_ASSESSED

=== 3. Download PDF Report ===
PDF Stream generated successfully, size: 53803 bytes

=== 4. Verify Record in History ===
Record found in history: True

=== 5. Verify Merchant and Officer Access is DENIED (403) ===
Merchant check status: 403 Insufficient privileges for this operation.
Officer check status: 403 Insufficient privileges for this operation.

=== 6. Verify Unauthenticated Request is REJECTED (401/403) ===
Unauthenticated check status: 401
```

---

## 5. Summary of Files Changed

1. [`backend/api/analyze.py`](file:///d:/SIH/Legal%20Metrology%20Compliance%20AI%20Prototype/backend/api/analyze.py) — Updated `require_roles(ROLE_USER, "NORMAL_USER", "USER", ROLE_ADMIN)` on `/api/analyze/manual`.
2. [`backend/tests/test_nu06_consumer_manual_product_check.py`](file:///d:/SIH/Legal%20Metrology%20Compliance%20AI%20Prototype/backend/tests/test_nu06_consumer_manual_product_check.py) — Added comprehensive test cases verifying canonical and alias role acceptance alongside strict 403/401 enforcement for merchant, officer, and anonymous callers.
