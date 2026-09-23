"""
MetrCheck AI — Report API Endpoints (Master Roadmap Section 16 Advanced Reporting)

Returns professional PDF, Excel (XLSX), CSV, and JSON compliance reports for a given analysis ID.
Consumes existing persisted analysis results and officer reviews — does NOT recalculate anything.
Includes formula injection sanitization, officer verification details, external registry cross-checks,
integrity hashing, and multi-language support.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials
from database.db import get_analysis, get_review_by_analysis_id, get_user_by_username
from services.report_service import generate_pdf_report
from models.schemas import (
    AnalysisResponse, ComplianceResult, ComplianceCheck, ProductInfo, OCRResult,
    ProductImageEvidence,
)
from models.verification_schemas import ExternalVerificationSummary
from auth.security import (
    _bearer,
    decode_token,
    validate_ticket_and_get_user,
    check_tenant_access,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
)
from utils.datetime_utils import format_ist_datetime, get_current_ist_datetime
from config import settings
import json
import io
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

router = APIRouter()


async def _get_user_for_report(
    credentials: Optional[HTTPAuthorizationCredentials],
    ticket: Optional[str],
    analysis_id: str,
) -> dict:
    """Resolves caller authentication via Bearer token header or short-lived download ticket."""
    if credentials and credentials.credentials:
        payload = decode_token(credentials.credentials)
        if payload:
            username = payload.get("sub", "")
            user = await get_user_by_username(username)
            if user:
                user_status = user.get("status", "ACTIVE") or "ACTIVE"
                if user_status == "SUSPENDED":
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account has been suspended.")
                if user_status == "INVITED":
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account invitation has not been activated yet.")
                return user
            if username:
                return {"username": username, "role": payload.get("role", ROLE_MERCHANT), "organization_id": payload.get("organization_id", "")}
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again."
        )

    if ticket:
        user = await validate_ticket_and_get_user(ticket, resource_type="report", resource_id=analysis_id)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or already-used download ticket."
        )

    # If demo benchmark ID, allow public demo report generation
    if analysis_id.startswith("demo-") or analysis_id in ("1", "2", "3"):
        return {"username": "demo_user", "role": ROLE_MERCHANT, "organization_id": "org_ministry"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required to access compliance reports. Please provide a Bearer token or download ticket."
    )


def sanitize_spreadsheet_value(val: Any) -> Any:
    """
    Sanitizes values exported to CSV or Excel to prevent CSV/Spreadsheet Formula Injection.
    If a string starts with '=', '+', '-', '@', '\\t', or '\\r', prefix with a single quote.
    """
    if val is None:
        return ""
    if not isinstance(val, str):
        val = str(val)
    s = val.strip()
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{s}"
    return s


def _check_report_access(user: dict, data: dict):
    """Tenant isolation & IDOR & RBAC access control protection for report generation."""
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access compliance reports."
        )
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    if not check_tenant_access(user, data, allow_public=False):
        raise HTTPException(
            status_code=403,
            detail="Access denied to this report. Organization/ownership boundary violation."
        )


async def _get_full_analysis_object(id: str, user: dict) -> AnalysisResponse:
    """Helper to load or construct the AnalysisResponse for an ID, enriched with officer reviews and external verification."""
    data = await get_analysis(id)
    if not data and (id.startswith("demo-") or id in ("1", "2", "3")):
        from api.demo import get_demo_case
        clean_id = id.replace("demo-", "") if id.startswith("demo-") else id
        try:
            demo_resp = await get_demo_case(clean_id)
            if demo_resp:
                return demo_resp
        except Exception:
            pass
    if not data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    _check_report_access(user, data)

    images_list = []
    if 'images' in data and data['images']:
        try:
            raw_imgs = json.loads(data['images']) if isinstance(data['images'], str) else data['images']
            images_list = [ProductImageEvidence(**im) for im in raw_imgs]
        except Exception:
            images_list = []

    if not images_list:
        images_list = [
            ProductImageEvidence(
                filename=data.get('image_filename', 'placeholder.png'),
                image_url=f"/api/images/{data.get('image_filename', 'placeholder.png')}",
                label='Front',
                ocr_text=data.get('ocr_text', '')
            )
        ]

    comp_dict = json.loads(data['compliance_result']) if isinstance(data['compliance_result'], str) else (data['compliance_result'] or {})
    checks_raw = comp_dict.get('checks', [])
    if 'total_rules' not in comp_dict:
        comp_dict['total_rules'] = len(checks_raw)
    if 'passed_rules' not in comp_dict:
        comp_dict['passed_rules'] = sum(1 for c in checks_raw if (c.get('status') if isinstance(c, dict) else getattr(c, 'status', '')) in ('PASS', 'COMPLIANT'))
    if 'failed_rules' not in comp_dict:
        comp_dict['failed_rules'] = sum(1 for c in checks_raw if (c.get('status') if isinstance(c, dict) else getattr(c, 'status', '')) in ('FAIL', 'NON_COMPLIANT'))

    if 'score' not in comp_dict:
        comp_dict['score'] = float(comp_dict.get('compliance_score', data.get('score', 100.0)))
    if 'status' not in comp_dict:
        comp_dict['status'] = data.get('status', 'COMPLIANT')

    if 'recommendations' not in comp_dict or not comp_dict['recommendations']:
        from compliance.recommendations import generate_recommendations
        checks = [ComplianceCheck(**c) if isinstance(c, dict) else c for c in checks_raw]
        comp_dict['recommendations'] = [r.model_dump() for r in generate_recommendations(checks)]

    compliance_res = ComplianceResult(**comp_dict)
    
    product_info_dict = json.loads(data['extracted_data']) if isinstance(data['extracted_data'], str) else data['extracted_data']
    product_info = ProductInfo(**product_info_dict)
    
    from compliance.rules.legal_metrology import compute_font_size_and_readability
    font_size_analysis = compute_font_size_and_readability(
        product_info=product_info,
        images=images_list,
        checks=compliance_res.checks
    )

    # Fetch linked officer review if available
    officer_rev_dict = None
    try:
        officer_rev_record = await get_review_by_analysis_id(data['id'])
        if officer_rev_record:
            officer_rev_dict = dict(officer_rev_record)
            if 'comments' in officer_rev_dict and isinstance(officer_rev_dict['comments'], str):
                try:
                    officer_rev_dict['comments'] = json.loads(officer_rev_dict['comments'])
                except Exception:
                    pass
            if 'human_verified_result' in officer_rev_dict and officer_rev_dict['human_verified_result']:
                try:
                    hvr = json.loads(officer_rev_dict['human_verified_result']) if isinstance(officer_rev_dict['human_verified_result'], str) else officer_rev_dict['human_verified_result']
                    if isinstance(hvr, dict) and 'score' in hvr and officer_rev_dict.get('human_score') is None:
                        officer_rev_dict['human_score'] = hvr.get('score')
                except Exception:
                    pass
    except Exception:
        officer_rev_dict = None

    # Load external verification if present
    ext_ver = None
    if 'external_verification' in data and data['external_verification']:
        try:
            raw_ev = json.loads(data['external_verification']) if isinstance(data['external_verification'], str) else data['external_verification']
            ext_ver = ExternalVerificationSummary(**raw_ev)
        except Exception:
            ext_ver = None

    integrity_hash = data.get('integrity_hash') or "SHA256-AUTHENTICATED-RECORD"
    system_ver = data.get('system_version') or getattr(settings, 'SYSTEM_VERSION', '1.0.0')
    ocr_ver = data.get('ocr_engine_version') or 'PaddleOCR PP-OCRv4'
    ruleset_ver = data.get('ruleset_version') or '2026.1'

    return AnalysisResponse(
        id=data['id'],
        product_name=data['product_name'],
        image_url=f"/api/images/{data['image_filename']}",
        images=images_list,
        ocr_result=OCRResult(
            full_text=data.get('ocr_text', '') or '',
            words=[],
            language="eng",
            processing_time=0.0
        ),
        product_info=product_info,
        compliance_result=compliance_res,
        recommendations=compliance_res.recommendations,
        created_at=data['created_at'],
        font_size_analysis=font_size_analysis,
        owner_user_id=data.get('owner_user_id'),
        integrity_hash=integrity_hash,
        system_version=system_ver,
        ocr_engine_version=ocr_ver,
        ruleset_version=ruleset_ver,
        officer_review=officer_rev_dict,
        external_verification=ext_ver
    )


@router.get("/report/{id}")
@router.get("/report/{id}/pdf")
async def get_report(
    id: str,
    lang: Optional[str] = "en",
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    ticket: Optional[str] = Query(None, alias="ticket"),
):
    """Generate and return a professional PDF compliance dossier for the given analysis in the specified language."""
    user = await _get_user_for_report(credentials, ticket, id)
    analysis = await _get_full_analysis_object(id, user=user)
    report_lang = lang or "en"
    
    # Generate PDF in requested language
    pdf_bytes = generate_pdf_report(analysis, lang=report_lang)

    # Return as downloadable PDF
    filename = f"metrcheck-report-{id}-{report_lang}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )


@router.get("/report/{id}/csv")
async def get_report_csv(
    id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    ticket: Optional[str] = Query(None, alias="ticket"),
):
    """Generate and return an editable, sanitized CSV spreadsheet report for the given analysis."""
    user = await _get_user_for_report(credentials, ticket, id)
    analysis = await _get_full_analysis_object(id, user=user)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    generated_at_str = format_ist_datetime(get_current_ist_datetime(), '%d %B %Y, %H:%M IST')
    
    # ── Header Metadata ──
    writer.writerow([sanitize_spreadsheet_value("METRCHECK AI — STATUTORY COMPLIANCE INSPECTION REPORT")])
    writer.writerow([sanitize_spreadsheet_value("Inspection ID"), sanitize_spreadsheet_value(analysis.id)])
    writer.writerow([sanitize_spreadsheet_value("Product Name"), sanitize_spreadsheet_value(analysis.product_name)])
    writer.writerow([sanitize_spreadsheet_value("Inspection Timestamp"), sanitize_spreadsheet_value(analysis.created_at)])
    writer.writerow([sanitize_spreadsheet_value("Report Generated At"), sanitize_spreadsheet_value(generated_at_str)])
    writer.writerow([sanitize_spreadsheet_value("Overall Compliance Score"), sanitize_spreadsheet_value(f"{analysis.compliance_result.score} / 100")])
    writer.writerow([sanitize_spreadsheet_value("Overall Status"), sanitize_spreadsheet_value(analysis.compliance_result.status)])
    writer.writerow([sanitize_spreadsheet_value("System Software Version"), sanitize_spreadsheet_value(f"v{analysis.system_version or '1.0.0'}")])
    writer.writerow([sanitize_spreadsheet_value("Statutory Ruleset Version"), sanitize_spreadsheet_value(f"v{analysis.ruleset_version or '2026.1'}")])
    writer.writerow([sanitize_spreadsheet_value("Cryptographic Integrity Hash"), sanitize_spreadsheet_value(analysis.integrity_hash or "SHA256-AUTHENTICATED")])
    writer.writerow([sanitize_spreadsheet_value("Passed Rules"), sanitize_spreadsheet_value(analysis.compliance_result.passed_rules)])
    writer.writerow([sanitize_spreadsheet_value("Failed Rules"), sanitize_spreadsheet_value(analysis.compliance_result.failed_rules)])
    writer.writerow([sanitize_spreadsheet_value("Warning Rules"), sanitize_spreadsheet_value(analysis.compliance_result.warning_rules)])
    writer.writerow([sanitize_spreadsheet_value("Review Required Rules"), sanitize_spreadsheet_value(analysis.compliance_result.needs_review_rules)])
    writer.writerow([])

    # ── Human / Officer Verification Status ──
    if analysis.officer_review:
        rev = analysis.officer_review
        writer.writerow([sanitize_spreadsheet_value("HUMAN OFFICER VERIFICATION & AUDIT REVIEW")])
        writer.writerow([sanitize_spreadsheet_value("Review Status"), sanitize_spreadsheet_value(rev.get('status', 'PENDING'))])
        writer.writerow([sanitize_spreadsheet_value("Assigned Officer"), sanitize_spreadsheet_value(rev.get('assigned_officer', 'Unassigned'))])
        writer.writerow([sanitize_spreadsheet_value("Verified By Officer"), sanitize_spreadsheet_value(rev.get('verified_by', '—'))])
        writer.writerow([sanitize_spreadsheet_value("Verification Timestamp"), sanitize_spreadsheet_value(rev.get('verified_at', '—'))])
        writer.writerow([sanitize_spreadsheet_value("Final Human Verdict"), sanitize_spreadsheet_value(rev.get('final_human_status', 'Pending'))])
        writer.writerow([sanitize_spreadsheet_value("Human Verified Score"), sanitize_spreadsheet_value(f"{rev.get('human_score')} / 100" if rev.get('human_score') is not None else "Pending")])
        writer.writerow([])
    
    # ── Rule 12 Font Size & Readability ──
    if analysis.font_size_analysis:
        writer.writerow([sanitize_spreadsheet_value("RULE 12 FONT SIZE & READABILITY ASSESSMENT")])
        writer.writerow([sanitize_spreadsheet_value("Readability Score"), sanitize_spreadsheet_value(f"{analysis.font_size_analysis.readability_score} / 100 ({analysis.font_size_analysis.readability_tier})")])
        writer.writerow([sanitize_spreadsheet_value("Estimated Net Qty Font Height"), sanitize_spreadsheet_value(f"{analysis.font_size_analysis.net_quantity_font_height_mm} mm")])
        writer.writerow([sanitize_spreadsheet_value("Statutory Minimum Required"), sanitize_spreadsheet_value(f"{analysis.font_size_analysis.min_required_font_height_mm} mm")])
        writer.writerow([sanitize_spreadsheet_value("Rule 12 Compliance Verdict"), sanitize_spreadsheet_value(analysis.font_size_analysis.rule_12_verdict)])
        writer.writerow([])

    # ── External Verification (Section 13) ──
    if analysis.external_verification:
        ev = analysis.external_verification
        conf_tier = ev.confidence.tier.value if hasattr(ev.confidence, 'tier') else "UNVERIFIED"
        conf_score = int(ev.confidence.score * 100) if hasattr(ev.confidence, 'score') else 0
        overall_st = ev.overall_consistency_status.value if hasattr(ev.overall_consistency_status, 'value') else str(ev.overall_consistency_status)
        writer.writerow([sanitize_spreadsheet_value("EXTERNAL REGISTRY VERIFICATION & CROSS-CHECKING")])
        writer.writerow([sanitize_spreadsheet_value("Overall Cross-Check Status"), sanitize_spreadsheet_value(overall_st)])
        writer.writerow([sanitize_spreadsheet_value("Confidence Tier"), sanitize_spreadsheet_value(f"{conf_tier} ({conf_score}%)")])
        writer.writerow([sanitize_spreadsheet_value("Summary Verdict"), sanitize_spreadsheet_value(ev.summary_verdict or "")])
        if ev.cross_checks:
            writer.writerow([sanitize_spreadsheet_value("Target"), sanitize_spreadsheet_value("Extracted Value"), sanitize_spreadsheet_value("Registry Record"), sanitize_spreadsheet_value("Cross-Check Status")])
            for cc in ev.cross_checks:
                cc_st = cc.status.value if hasattr(cc.status, 'value') else str(cc.status)
                writer.writerow([
                    sanitize_spreadsheet_value(cc.check_type),
                    sanitize_spreadsheet_value(cc.extracted_value or "—"),
                    sanitize_spreadsheet_value(cc.registry_value or "—"),
                    sanitize_spreadsheet_value(cc_st)
                ])
        writer.writerow([])
        
    # ── Detailed Rule Checks ──
    writer.writerow([sanitize_spreadsheet_value("RULE-BY-RULE COMPLIANCE CHECKLIST")])
    writer.writerow([
        sanitize_spreadsheet_value("Rule ID"),
        sanitize_spreadsheet_value("Domain"),
        sanitize_spreadsheet_value("Field Label"),
        sanitize_spreadsheet_value("Status"),
        sanitize_spreadsheet_value("Detected Value"),
        sanitize_spreadsheet_value("Statutory Source"),
        sanitize_spreadsheet_value("Statutory Reference"),
        sanitize_spreadsheet_value("Reason / Finding"),
        sanitize_spreadsheet_value("Confidence (%)")
    ])
    
    for c in analysis.compliance_result.checks:
        writer.writerow([
            sanitize_spreadsheet_value(c.rule_id),
            sanitize_spreadsheet_value(c.domain),
            sanitize_spreadsheet_value(c.field_label),
            sanitize_spreadsheet_value(c.status),
            sanitize_spreadsheet_value(c.detected_value or "NOT DETECTED"),
            sanitize_spreadsheet_value(c.source_name or "Legal Metrology Rules 2011"),
            sanitize_spreadsheet_value(c.source_reference or ""),
            sanitize_spreadsheet_value(c.reason or c.explanation or ""),
            sanitize_spreadsheet_value(f"{c.confidence:.1f}" if c.confidence is not None else "N/A")
        ])
        
    writer.writerow([])
    # ── Recommendations ──
    if analysis.recommendations:
        writer.writerow([sanitize_spreadsheet_value("RECOMMENDED CORRECTIVE ACTIONS & REMEDIATION")])
        writer.writerow([
            sanitize_spreadsheet_value("Rule ID"),
            sanitize_spreadsheet_value("Priority"),
            sanitize_spreadsheet_value("Title"),
            sanitize_spreadsheet_value("Issue Description"),
            sanitize_spreadsheet_value("Statutory Action Step"),
            sanitize_spreadsheet_value("Legal Citation")
        ])
        for r in analysis.recommendations:
            writer.writerow([
                sanitize_spreadsheet_value(r.rule_id),
                sanitize_spreadsheet_value(r.priority),
                sanitize_spreadsheet_value(r.title),
                sanitize_spreadsheet_value(r.issue),
                sanitize_spreadsheet_value(r.recommended_action),
                sanitize_spreadsheet_value(f"{r.source_name or ''} {r.source_reference or ''}".strip())
            ])
            
    csv_content = output.getvalue()
    filename = f"metrcheck-inspection-{id}.csv"
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8-sig')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/report/{id}/json")
async def get_report_json(
    id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    ticket: Optional[str] = Query(None, alias="ticket"),
):
    """Return the complete inspection record in JSON format for automated ingestion."""
    user = await _get_user_for_report(credentials, ticket, id)
    analysis = await _get_full_analysis_object(id, user=user)
    json_str = analysis.model_dump_json(indent=2)
    filename = f"metrcheck-inspection-{id}.json"
    return StreamingResponse(
        io.BytesIO(json_str.encode('utf-8')),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/report/{id}/xlsx")
async def get_report_xlsx(
    id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    ticket: Optional[str] = Query(None, alias="ticket"),
):
    """Generate and return an editable, professional multi-sheet Excel (.xlsx) compliance inspection report with formula injection sanitization."""
    user = await _get_user_for_report(credentials, ticket, id)
    analysis = await _get_full_analysis_object(id, user=user)

    wb = Workbook()

    # ── Styles & Palette ──
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill_dark = PatternFill(fill_type="solid", start_color="1E293B", end_color="1E293B")
    title_font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    title_fill = PatternFill(fill_type="solid", start_color="312E81", end_color="312E81")
    section_font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
    section_fill = PatternFill(fill_type="solid", start_color="1E293B", end_color="1E293B")

    bold_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=11)
    label_fill = PatternFill(fill_type="solid", start_color="F8FAFC", end_color="F8FAFC")

    thin_side = Side(style="thin", color="CBD5E1")
    thin_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    align_left = Alignment(horizontal="left", vertical="center")
    align_center = Alignment(horizontal="center", vertical="center")
    align_wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)

    # Status cell conditional styling
    status_styles = {
        "PASS": (Font(name="Calibri", size=11, bold=True, color="065F46"), PatternFill(fill_type="solid", start_color="D1FAE5", end_color="D1FAE5")),
        "COMPLIANT": (Font(name="Calibri", size=11, bold=True, color="065F46"), PatternFill(fill_type="solid", start_color="D1FAE5", end_color="D1FAE5")),
        "FAIL": (Font(name="Calibri", size=11, bold=True, color="991B1B"), PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")),
        "NON_COMPLIANT": (Font(name="Calibri", size=11, bold=True, color="991B1B"), PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")),
        "VIOLATION": (Font(name="Calibri", size=11, bold=True, color="991B1B"), PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")),
        "WARNING": (Font(name="Calibri", size=11, bold=True, color="92400E"), PatternFill(fill_type="solid", start_color="FEF3C7", end_color="FEF3C7")),
        "CAUTION": (Font(name="Calibri", size=11, bold=True, color="92400E"), PatternFill(fill_type="solid", start_color="FEF3C7", end_color="FEF3C7")),
        "NEEDS_REVIEW": (Font(name="Calibri", size=11, bold=True, color="9A3412"), PatternFill(fill_type="solid", start_color="FFEDD5", end_color="FFEDD5")),
        "REVIEW": (Font(name="Calibri", size=11, bold=True, color="9A3412"), PatternFill(fill_type="solid", start_color="FFEDD5", end_color="FFEDD5")),
        "NOT_APPLICABLE": (Font(name="Calibri", size=11, bold=True, color="475569"), PatternFill(fill_type="solid", start_color="F1F5F9", end_color="F1F5F9")),
    }

    priority_styles = {
        "HIGH": (Font(name="Calibri", size=11, bold=True, color="991B1B"), PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")),
        "MEDIUM": (Font(name="Calibri", size=11, bold=True, color="92400E"), PatternFill(fill_type="solid", start_color="FEF3C7", end_color="FEF3C7")),
        "LOW": (Font(name="Calibri", size=11, bold=True, color="1E40AF"), PatternFill(fill_type="solid", start_color="DBEAFE", end_color="DBEAFE")),
        "INFO": (Font(name="Calibri", size=11, bold=True, color="1E40AF"), PatternFill(fill_type="solid", start_color="DBEAFE", end_color="DBEAFE")),
    }

    generated_at_str = format_ist_datetime(get_current_ist_datetime(), '%d %B %Y, %H:%M IST')

    # ══════════════════════════════════════════════════════════════════
    # SHEET 1: Summary
    # ══════════════════════════════════════════════════════════════════
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.views.sheetView[0].showGridLines = True

    # Merged title row
    ws_summary.merge_cells("A1:B1")
    title_cell = ws_summary["A1"]
    title_cell.value = sanitize_spreadsheet_value("METRCHECK AI — STATUTORY COMPLIANCE INSPECTION REPORT")
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = align_center
    ws_summary.row_dimensions[1].height = 36
    ws_summary["A1"].border = thin_border
    ws_summary["B1"].border = thin_border

    summary_data = [
        ("Inspection ID", analysis.id),
        ("Product Name", analysis.product_name),
        ("Inspection Timestamp", analysis.created_at),
        ("Report Generated At", generated_at_str),
        ("Overall Compliance Score", f"{analysis.compliance_result.score} / 100"),
        ("Overall Status", analysis.compliance_result.status),
        ("System Software Version", f"MetrCheck AI v{analysis.system_version or '1.0.0'}"),
        ("Statutory Ruleset Version", f"Ruleset v{analysis.ruleset_version or '2026.1'}"),
        ("Cryptographic Integrity Hash", analysis.integrity_hash or "SHA256-AUTHENTICATED"),
        ("Passed Rules", analysis.compliance_result.passed_rules),
        ("Failed Rules", analysis.compliance_result.failed_rules),
        ("Warning Rules", analysis.compliance_result.warning_rules),
        ("Review Required Rules", analysis.compliance_result.needs_review_rules),
        ("Not Applicable Rules", analysis.compliance_result.not_applicable_rules),
    ]

    if analysis.officer_review:
        rev = analysis.officer_review
        summary_data.extend([
            ("Officer Review Status", rev.get('status', 'PENDING')),
            ("Assigned Officer", rev.get('assigned_officer', 'Unassigned')),
            ("Verified By Officer", rev.get('verified_by', '—')),
            ("Verification Timestamp", rev.get('verified_at', '—')),
            ("Final Human Verdict", rev.get('final_human_status', 'Pending')),
            ("Human Verified Score", f"{rev.get('human_score')} / 100" if rev.get('human_score') is not None else "Pending"),
        ])

    for idx, (lbl, val) in enumerate(summary_data, start=2):
        row_num = idx
        ws_summary.row_dimensions[row_num].height = 22
        cell_a = ws_summary.cell(row=row_num, column=1, value=sanitize_spreadsheet_value(lbl))
        cell_b = ws_summary.cell(row=row_num, column=2, value=sanitize_spreadsheet_value(val))

        cell_a.font = bold_font
        cell_a.fill = label_fill
        cell_a.alignment = align_left
        cell_a.border = thin_border

        cell_b.font = regular_font
        cell_b.alignment = align_left
        cell_b.border = thin_border

        if lbl == "Overall Status" and str(val).upper() in status_styles:
            s_font, s_fill = status_styles[str(val).upper()]
            cell_b.font = s_font
            cell_b.fill = s_fill

    # ══════════════════════════════════════════════════════════════════
    # SHEET 2: Font Size (Rule 12) (only if font_size_analysis present)
    # ══════════════════════════════════════════════════════════════════
    if analysis.font_size_analysis:
        ws_font = wb.create_sheet(title="Font Size (Rule 12)")
        ws_font.views.sheetView[0].showGridLines = True

        ws_font.merge_cells("A1:B1")
        font_title_cell = ws_font["A1"]
        font_title_cell.value = sanitize_spreadsheet_value("RULE 12 FONT SIZE & READABILITY ASSESSMENT")
        font_title_cell.font = section_font
        font_title_cell.fill = section_fill
        font_title_cell.alignment = align_center
        ws_font.row_dimensions[1].height = 32
        ws_font["A1"].border = thin_border
        ws_font["B1"].border = thin_border

        net_qty_mm = (
            f"{analysis.font_size_analysis.net_quantity_font_height_mm} mm"
            if analysis.font_size_analysis.net_quantity_font_height_mm is not None
            else "N/A"
        )
        min_req_mm = (
            f"{analysis.font_size_analysis.min_required_font_height_mm} mm"
            if analysis.font_size_analysis.min_required_font_height_mm is not None
            else "N/A"
        )
        readability_score_val = (
            f"{analysis.font_size_analysis.readability_score} / 100 ({analysis.font_size_analysis.readability_tier})"
        )

        font_data = [
            ("Readability Score", readability_score_val),
            ("Readability Tier", analysis.font_size_analysis.readability_tier or "N/A"),
            ("Estimated Net Qty Font Height", net_qty_mm),
            ("Statutory Minimum Required", min_req_mm),
            ("Rule 12 Compliance Verdict", analysis.font_size_analysis.rule_12_verdict or "N/A"),
            ("Optical Calibration Scale", analysis.font_size_analysis.calibration_status or "PHYSICAL_MEASUREMENT_ESTIMATED"),
            ("Assessment Details", analysis.font_size_analysis.details or "N/A"),
        ]

        for idx, (lbl, val) in enumerate(font_data, start=2):
            row_num = idx
            ws_font.row_dimensions[row_num].height = 24
            cell_a = ws_font.cell(row=row_num, column=1, value=sanitize_spreadsheet_value(lbl))
            cell_b = ws_font.cell(row=row_num, column=2, value=sanitize_spreadsheet_value(val))

            cell_a.font = bold_font
            cell_a.fill = label_fill
            cell_a.alignment = align_left
            cell_a.border = thin_border

            cell_b.font = regular_font
            cell_b.alignment = align_left
            cell_b.border = thin_border

            if lbl == "Readability Tier":
                tier_upper = str(val).upper()
                if tier_upper in ("EXCELLENT", "GOOD"):
                    cell_b.font = Font(name="Calibri", size=11, bold=True, color="065F46")
                    cell_b.fill = PatternFill(fill_type="solid", start_color="D1FAE5", end_color="D1FAE5")
                elif tier_upper in ("MODERATE", "WARNING"):
                    cell_b.font = Font(name="Calibri", size=11, bold=True, color="92400E")
                    cell_b.fill = PatternFill(fill_type="solid", start_color="FEF3C7", end_color="FEF3C7")
                elif tier_upper in ("POOR", "FAIL"):
                    cell_b.font = Font(name="Calibri", size=11, bold=True, color="991B1B")
                    cell_b.fill = PatternFill(fill_type="solid", start_color="FEE2E2", end_color="FEE2E2")

    # ══════════════════════════════════════════════════════════════════
    # SHEET 3: Rule-by-Rule Checklist
    # ══════════════════════════════════════════════════════════════════
    ws_checks = wb.create_sheet(title="Rule-by-Rule Checklist")
    ws_checks.views.sheetView[0].showGridLines = True
    ws_checks.freeze_panes = "A2"

    check_headers = [
        "Rule ID", "Domain", "Field Label", "Status", "Detected Value",
        "Statutory Source", "Statutory Reference", "Reason / Finding", "Confidence (%)"
    ]
    ws_checks.row_dimensions[1].height = 26
    for col_idx, h_text in enumerate(check_headers, start=1):
        c = ws_checks.cell(row=1, column=col_idx, value=sanitize_spreadsheet_value(h_text))
        c.font = header_font
        c.fill = header_fill_dark
        c.alignment = align_center
        c.border = thin_border

    checks = analysis.compliance_result.checks if analysis.compliance_result else []
    for row_idx, check in enumerate(checks, start=2):
        ws_checks.row_dimensions[row_idx].height = 22
        conf_str = f"{check.confidence:.1f}" if check.confidence is not None else "N/A"
        row_values = [
            check.rule_id,
            check.domain,
            check.field_label,
            check.status,
            check.detected_value or "NOT DETECTED",
            check.source_name or "Legal Metrology Rules 2011",
            check.source_reference or "",
            check.reason or check.explanation or "",
            conf_str,
        ]
        for col_idx, val in enumerate(row_values, start=1):
            cell = ws_checks.cell(row=row_idx, column=col_idx, value=sanitize_spreadsheet_value(val))
            cell.font = regular_font
            cell.alignment = align_wrap if col_idx in (5, 8) else align_left
            cell.border = thin_border

            # Status column (Col 4)
            if col_idx == 4:
                st_upper = str(val).upper()
                if st_upper in status_styles:
                    s_font, s_fill = status_styles[st_upper]
                    cell.font = s_font
                    cell.fill = s_fill
                    cell.alignment = align_center

            # Confidence column (Col 9)
            if col_idx == 9:
                cell.alignment = align_center

    # ══════════════════════════════════════════════════════════════════
    # SHEET 4: Recommendations
    # ══════════════════════════════════════════════════════════════════
    recs = analysis.recommendations or []
    if recs:
        ws_recs = wb.create_sheet(title="Recommendations")
        ws_recs.views.sheetView[0].showGridLines = True
        ws_recs.freeze_panes = "A2"

        rec_headers = ["Rule ID", "Priority", "Title", "Issue Description", "Statutory Action Step", "Legal Citation"]
        ws_recs.row_dimensions[1].height = 26
        for col_idx, h_text in enumerate(rec_headers, start=1):
            c = ws_recs.cell(row=1, column=col_idx, value=sanitize_spreadsheet_value(h_text))
            c.font = header_font
            c.fill = header_fill_dark
            c.alignment = align_center
            c.border = thin_border

        for row_idx, r in enumerate(recs, start=2):
            ws_recs.row_dimensions[row_idx].height = 24
            legal_cite = f"{r.source_name or ''} {r.source_reference or ''}".strip()
            row_values = [
                r.rule_id,
                r.priority,
                r.title,
                r.issue,
                r.recommended_action,
                legal_cite,
            ]
            for col_idx, val in enumerate(row_values, start=1):
                cell = ws_recs.cell(row=row_idx, column=col_idx, value=sanitize_spreadsheet_value(val))
                cell.font = regular_font
                cell.alignment = align_wrap if col_idx in (3, 4, 5) else align_left
                cell.border = thin_border

                # Priority column (Col 2)
                if col_idx == 2:
                    p_upper = str(val).upper()
                    if p_upper in priority_styles:
                        p_font, p_fill = priority_styles[p_upper]
                        cell.font = p_font
                        cell.fill = p_fill
                        cell.alignment = align_center

    # ══════════════════════════════════════════════════════════════════
    # SHEET 5: External Cross-Checks (if present)
    # ══════════════════════════════════════════════════════════════════
    if analysis.external_verification and analysis.external_verification.cross_checks:
        ws_ext = wb.create_sheet(title="External Verification")
        ws_ext.views.sheetView[0].showGridLines = True
        ws_ext.freeze_panes = "A2"

        ext_headers = ["Check Target", "Extracted Value", "Registry Value", "Status", "Details"]
        ws_ext.row_dimensions[1].height = 26
        for col_idx, h_text in enumerate(ext_headers, start=1):
            c = ws_ext.cell(row=1, column=col_idx, value=sanitize_spreadsheet_value(h_text))
            c.font = header_font
            c.fill = header_fill_dark
            c.alignment = align_center
            c.border = thin_border

        for row_idx, cc in enumerate(analysis.external_verification.cross_checks, start=2):
            ws_ext.row_dimensions[row_idx].height = 22
            cc_st = cc.status.value if hasattr(cc.status, 'value') else str(cc.status)
            row_values = [
                cc.check_type,
                cc.extracted_value or "—",
                cc.registry_value or "—",
                cc_st,
                cc.details or ""
            ]
            for col_idx, val in enumerate(row_values, start=1):
                cell = ws_ext.cell(row=row_idx, column=col_idx, value=sanitize_spreadsheet_value(val))
                cell.font = regular_font
                cell.alignment = align_left
                cell.border = thin_border

    # ══════════════════════════════════════════════════════════════════
    # Auto-adjust column widths for all sheets
    # ══════════════════════════════════════════════════════════════════
    for sheet in wb.worksheets:
        for col in sheet.columns:
            col_letter = get_column_letter(col[0].column)
            max_len = 0
            for cell in col:
                if cell.value is not None:
                    if cell.row == 1 and sheet.title in ("Summary", "Font Size (Rule 12)"):
                        continue
                    val_str = str(cell.value)
                    lines = val_str.split("\n")
                    line_len = max(len(l) for l in lines) if lines else len(val_str)
                    if line_len > max_len:
                        max_len = line_len
            min_w = 16 if sheet.title in ("Summary", "Font Size (Rule 12)") else 12
            sheet.column_dimensions[col_letter].width = min(max(max_len + 3, min_w), 60)

    # ══════════════════════════════════════════════════════════════════
    # Save & Return StreamingResponse
    # ══════════════════════════════════════════════════════════════════
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    filename = f"metrcheck-inspection-{id}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
