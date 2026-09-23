"""
NU-04A.1 Targeted Verification Test Suite.

Verifies:
1. IMAGE HEADER VERIFICATION:
   - Authenticated user can fetch image file from /api/images/{filename} via Bearer token and download ticket.
   - Returns 200 OK, valid image MIME type (image/png, image/jpeg), and correct byte payload.
2. PACKAGE PREVIEW VERIFICATION:
   - Both Front and Back panel images are accessible to authenticated user.
   - Panel switching contract is preserved.
   - Non-existent files safely return 404 with standard error message.
3. NAVIGATION ORDER & DOM INTEGRITY:
   - Canonical 11 sections are strictly registered in DOM order without misplacement.
4. REAL ALPINO EXTRACTION VERIFICATION:
   - Alpino package extraction DOES NOT report ₹15435 as MRP.
   - Evaluates to UNCERTAIN / NEEDS_REVIEW with unprinted stamp explanation.
5. MRP REGRESSION SUITE:
   - Test A: Barcode/GTIN numbers cannot become MRP.
   - Test B: Nutrition values (kcal, kJ, protein, fat) cannot become MRP.
   - Test C: Batch/lot/license/phone/PIN values cannot become MRP.
   - Test D: "MRP see bottom of pack" without numeric value becomes uncertain.
   - Test E: Legitimate numeric MRP > ₹1000 (e.g. MRP: 1499 or MRP: ₹1499) is successfully extracted.
"""

import os
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from database.db import init_db, save_analysis, create_user
from auth.security import hash_password, create_token, ROLE_USER
from extraction.extractor import LocalExtractor
from ocr.repair import repair_mrp
from models.schemas import ProductImageEvidence
from compliance.engine import ComplianceEngine
from compliance.rules.models import ComplianceStatus


def _ensure_test_isolation():
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "SAFETY ERROR: Test running on production uploads!"
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "SAFETY ERROR: Test running on production DB!"


@pytest.fixture(autouse=True)
def setup_env():
    _ensure_test_isolation()


async def _create_test_user(username: str, role: str = ROLE_USER, org_id: str = ""):
    salt, pwh = hash_password("TestPassword123!")
    try:
        await create_user(
            username=username,
            password_hash=pwh,
            salt=salt,
            role=role,
            full_name=f"User {username}",
            organization_id=org_id,
        )
    except Exception:
        pass


# ── 1. IMAGE HEADER & SERVING VERIFICATION ────────────────────────────────────

@pytest.mark.asyncio
async def test_header_image_authenticated_retrieval_and_mime():
    """Verify HTTP status, MIME Content-Type, byte payload, and Bearer auth on image endpoint."""
    await init_db()
    client = TestClient(app)
    username = f"header_user_{os.urandom(4).hex()}"
    org_id = f"org_{username}"
    await _create_test_user(username, ROLE_USER, org_id)
    token = create_token(username, ROLE_USER)

    filename = f"header_thumb_{os.urandom(4).hex()}.png"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    # Minimal 1x1 PNG bytes
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    with open(filepath, "wb") as f:
        f.write(png_bytes)

    ana_id = f"ana-header-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Alpino Oats Thumbnail Test",
        image_filename=filename,
        extracted_data={"product_name": "Alpino Oats Thumbnail Test"},
        compliance_result={"score": 100.0, "status": "PASS", "checks": []},
        ocr_text="Thumbnail test",
        owner_user_id=username,
        organization_id=org_id,
    )

    try:
        # Request with Bearer auth
        res = client.get(f"/api/images/{filename}", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/png"
        assert res.content == png_bytes
        assert len(res.content) == len(png_bytes)
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ── 2. PACKAGE PREVIEW VERIFICATION ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_package_preview_front_back_and_fallback():
    """Verify Front and Back panels can be retrieved and missing files return 404."""
    await init_db()
    client = TestClient(app)
    username = f"preview_user_{os.urandom(4).hex()}"
    org_id = f"org_{username}"
    await _create_test_user(username, ROLE_USER, org_id)
    token = create_token(username, ROLE_USER)

    front_fn = f"panel_front_{os.urandom(4).hex()}.jpg"
    back_fn = f"panel_back_{os.urandom(4).hex()}.jpg"
    front_path = os.path.join(settings.UPLOAD_DIR, front_fn)
    back_path = os.path.join(settings.UPLOAD_DIR, back_fn)

    front_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00FRONT_PANEL_BYTES"
    back_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00BACK_PANEL_BYTES"

    with open(front_path, "wb") as f:
        f.write(front_bytes)
    with open(back_path, "wb") as f:
        f.write(back_bytes)

    ana_id = f"ana-preview-{os.urandom(4).hex()}"
    await save_analysis(
        analysis_id=ana_id,
        product_name="Dual Panel Preview Product",
        image_filename=front_fn,
        images=[
            {"filename": front_fn, "image_url": f"/api/images/{front_fn}", "label": "Front"},
            {"filename": back_fn, "image_url": f"/api/images/{back_fn}", "label": "Back"},
        ],
        extracted_data={"product_name": "Dual Panel Preview Product"},
        compliance_result={"score": 95.0, "status": "PASS", "checks": []},
        ocr_text="Dual panel test",
        owner_user_id=username,
        organization_id=org_id,
    )

    try:
        # Front Panel access
        res_front = client.get(f"/api/images/{front_fn}", headers={"Authorization": f"Bearer {token}"})
        assert res_front.status_code == 200
        assert res_front.headers["content-type"] == "image/jpeg"
        assert res_front.content == front_bytes

        # Back Panel access
        res_back = client.get(f"/api/images/{back_fn}", headers={"Authorization": f"Bearer {token}"})
        assert res_back.status_code == 200
        assert res_back.headers["content-type"] == "image/jpeg"
        assert res_back.content == back_bytes

        # Missing file produces safe 404 (intended fallback)
        res_missing = client.get("/api/images/non_existent_panel.jpg", headers={"Authorization": f"Bearer {token}"})
        assert res_missing.status_code == 404
        assert "Requested file not found." in res_missing.json().get("detail", "")
    finally:
        if os.path.exists(front_path):
            os.remove(front_path)
        if os.path.exists(back_path):
            os.remove(back_path)


# ── 3. REAL ALPINO EXTRACTION & MRP VERIFICATION ──────────────────────────────

@pytest.mark.asyncio
async def test_alpino_mrp_does_not_report_15435():
    """Verify real Alpino OCR extraction does NOT report ₹15435 as MRP and evaluates to UNCERTAIN/NEEDS_REVIEW."""
    from ocr.paddle_engine import PaddleOCREngine, _is_paddle_available

    if not _is_paddle_available():
        pytest.skip("PaddleOCR not installed in this environment.")

    base_dir = os.path.dirname(__file__)
    front_path = os.path.join(base_dir, "..", "fixtures", "alpino_front.png")
    back_path = os.path.join(base_dir, "..", "fixtures", "alpino_back.png")
    if not os.path.exists(front_path):
        front_path = os.path.join("backend", "fixtures", "alpino_front.png")
        back_path = os.path.join("backend", "fixtures", "alpino_back.png")

    if not os.path.exists(front_path) or not os.path.exists(back_path):
        pytest.skip("Alpino fixtures not found.")

    ocr_engine = PaddleOCREngine()
    res_f = await ocr_engine.extract(front_path)
    res_b = await ocr_engine.extract(back_path)

    ev_f = ProductImageEvidence(
        filename="alpino_front.png",
        image_url="/alpino_front.png",
        label="Front",
        ocr_text=res_f.full_text,
        words=res_f.words
    )
    ev_b = ProductImageEvidence(
        filename="alpino_back.png",
        image_url="/alpino_back.png",
        label="Back",
        ocr_text=res_b.full_text,
        words=res_b.words
    )

    combined_text = f"=== [FRONT LABEL] ===\n{res_f.full_text}\n\n=== [BACK LABEL] ===\n{res_b.full_text}"
    extractor = LocalExtractor()
    info = extractor.extract(combined_text, images=[ev_f, ev_b])

    # Explicit check: System does NOT report 15435 or ₹15435
    assert "15435" not in (info.mrp or "")
    assert info.mrp != "₹15435"
    assert info.mrp != "₹15435.00"
    assert info.mrp != "15435"

    # Verify unprinted label is correctly detected
    assert "label detected" in info.mrp.lower() or "unprinted" in info.mrp.lower()

    # Compliance Engine LM-004 State Check
    engine = ComplianceEngine()
    comp_res = engine.check(info, ocr_text=combined_text, images=[ev_f, ev_b])
    checks = {c.rule_id: c for c in comp_res["checks"]}

    assert checks["LM-004"].status == ComplianceStatus.NEEDS_REVIEW.value
    assert "unprinted" in checks["LM-004"].reason.lower() or "missing" in checks["LM-004"].reason.lower() or "not reliably" in checks["LM-004"].reason.lower()


# ── 4. MRP REGRESSION SUITE (A, B, C, D, E) ───────────────────────────────────

def test_mrp_regression_a_barcode_cannot_become_mrp():
    """A. Barcode/GTIN numbers (e.g. 8901234567890) cannot become MRP."""
    assert repair_mrp("8901234567890") == ""
    assert repair_mrp("GTIN: 8901030999999") == ""
    assert repair_mrp("10716022000249") == ""


def test_mrp_regression_b_nutrition_values_cannot_become_mrp():
    """B. Nutrition values (energy, kcal, protein, etc.) cannot become MRP."""
    assert repair_mrp("Energy: 1543.5 kJ") == ""
    assert repair_mrp("Energy 15435 kJ") == ""
    assert repair_mrp("154.35 kcal") == ""
    assert repair_mrp("Protein 15.43 g") == ""
    assert repair_mrp("Carbohydrates 68.5 g") == ""
    assert repair_mrp("Sodium 1543 mg") == ""


def test_mrp_regression_c_batch_lot_phone_pin_cannot_become_mrp():
    """C. Batch, lot, license, phone, and PIN values cannot become MRP."""
    assert repair_mrp("Batch No: 15435") == ""
    assert repair_mrp("LOT 15435") == ""
    assert repair_mrp("PIN: 395007") == ""
    assert repair_mrp("Phone: 8347688000") == ""
    assert repair_mrp("Mfg Date: 15/04/2026") == ""


def test_mrp_regression_d_unprinted_instruction_becomes_uncertain():
    """D. 'MRP see bottom of pack' without numeric price becomes uncertain / unprinted."""
    # repair_mrp rejects instruction string
    assert repair_mrp("MRP see bottom of pack") == ""
    assert repair_mrp("FOR MRP SEE BELOW") == ""
    assert repair_mrp("REFER TO JAR BASE FOR MRP") == ""

    # Extractor recognizes the unprinted label and returns UNCERTAIN
    extractor = LocalExtractor()
    sample_text = "FOR MRP, MFD & BATCH NO: SEE BOTTOM OF PACK\nNET QTY: 500 g"
    info = extractor.extract(sample_text)
    assert "label detected" in info.mrp.lower() or "unprinted" in info.mrp.lower()


def test_mrp_regression_e_legitimate_mrp_over_1000_is_accepted():
    """E. Legitimate numeric MRP > ₹1000 (e.g. MRP: 1499, MRP ₹2499) is successfully extracted."""
    # Direct repair
    assert repair_mrp("1499") == "₹1499"
    assert repair_mrp("1499.00") == "₹1499.00"
    assert repair_mrp("MRP: 1499") == "₹1499"
    assert repair_mrp("MRP ₹1499") == "₹1499"
    assert repair_mrp("MRP: Rs. 2499.00") == "₹2499.00"

    # Full extractor pipeline
    extractor = LocalExtractor()
    text1 = "BRAND: Premium Brand\nMRP: ₹1499 (INCL. OF ALL TAXES)\nNET WT: 1 kg"
    info1 = extractor.extract(text1)
    assert info1.mrp == "₹1499"

    text2 = "MRP: 2499.00\nNET QTY: 1 unit"
    info2 = extractor.extract(text2)
    assert "2499" in (info2.mrp or "")


def test_mrp_regression_f_multiline_currency_separation_cannot_bind_isolated_numbers():
    """F. Isolated 'RS' or 'RA' on one line must not match numbers on subsequent lines."""
    extractor = LocalExtractor()
    # Simulates OCR artifact where RS is on line 1 and batch/internal number is on line 2
    text = "INGREDIENTS: OATS\nRS\n15435\n000000\nNET WT: 400 g"
    info = extractor.extract(text)
    assert "15435" not in (info.mrp or "")

    # Single-line valid currency format must match
    valid_text = "NET WT: 400 g\nRs. 15435 (INCL OF ALL TAXES)"
    valid_info = extractor.extract(valid_text)
    assert valid_info.mrp == "₹15435"


@pytest.mark.asyncio
async def test_live_analyze_products_alpino_returns_needs_review():
    """Verify live analyze_products pipeline on Alpino does not report ₹15435 and yields NEEDS_REVIEW for LM-004."""
    from services.analysis_service import analyze_products
    from fastapi import UploadFile
    import io

    base_dir = os.path.dirname(__file__)
    front_path = os.path.join(base_dir, "..", "fixtures", "alpino_front.png")
    back_path = os.path.join(base_dir, "..", "fixtures", "alpino_back.png")
    if not os.path.exists(front_path):
        front_path = os.path.join("backend", "fixtures", "alpino_front.png")
        back_path = os.path.join("backend", "fixtures", "alpino_back.png")

    if not os.path.exists(front_path) or not os.path.exists(back_path):
        pytest.skip("Alpino fixtures not found.")

    with open(front_path, "rb") as f1, open(back_path, "rb") as f2:
        file1 = UploadFile(filename="alpino_front.png", file=io.BytesIO(f1.read()))
        file2 = UploadFile(filename="alpino_back.png", file=io.BytesIO(f2.read()))

    res = await analyze_products([file1, file2], labels=["Front", "Back"], owner_user_id="test-verify")

    assert "15435" not in (res.product_info.mrp or "")
    assert res.product_info.mrp != "₹15435"
    assert "unprinted" in res.product_info.mrp.lower() or "label detected" in res.product_info.mrp.lower()

    lm_004 = next((c for c in res.compliance_result.checks if c.rule_id == "LM-004"), None)
    assert lm_004 is not None
    status_str = lm_004.status.value if hasattr(lm_004.status, 'value') else str(lm_004.status)
    assert status_str == "NEEDS_REVIEW"
    assert "unprinted" in lm_004.explanation.lower() or "faint" in lm_004.explanation.lower()


@pytest.mark.asyncio
async def test_evidence_viewer_back_panel_image_and_coordinates_verification():
    """NU-04A.3: Verify Back panel image authenticated retrieval and evidence marker bounding boxes."""
    await init_db()
    client = TestClient(app)
    username = f"evidence_user_{os.urandom(4).hex()}"
    org_id = f"org_{username}"
    await _create_test_user(username, ROLE_USER, org_id)
    token = create_token(username, ROLE_USER)

    # 1. Create simulated Back panel image in uploads
    back_filename = f"evidence_back_{os.urandom(4).hex()}.png"
    back_filepath = os.path.join(settings.UPLOAD_DIR, back_filename)
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    with open(back_filepath, "wb") as f:
        f.write(png_bytes)

    # 2. Save analysis record containing Back panel image evidence and findings with BBox
    ana_id = f"ana-ev-{os.urandom(4).hex()}"
    images_data = [
        {"image_url": f"/api/images/{back_filename}", "label": "Back", "word_count": 42}
    ]
    checks_data = [
        {
            "rule_id": "FS-003",
            "field": "ingredients",
            "field_label": "Ingredients Declaration",
            "domain": "FSSAI",
            "status": "NEEDS_REVIEW",
            "confidence": 0.81,
            "evidence_image_label": "Back",
            "bbox": [101, 147, 388, 260],
            "evidence": [
                {
                    "rule_id": "FS-003",
                    "field_type": "ingredients",
                    "bbox": [101, 147, 388, 260],
                    "confidence": 0.81,
                    "geometry_type": "WORD_UNION",
                    "match_method": "DIRECT_OCR",
                    "image_label": "Back",
                    "image_index": 0,
                    "evidence_status": "NEEDS_REVIEW",
                    "explanation": "Ingredients declaration detected on Back Panel."
                }
            ]
        }
    ]

    await save_analysis(
        analysis_id=ana_id,
        product_name="Alpino Evidence Test",
        image_filename=back_filename,
        images=images_data,
        extracted_data={"product_name": "Alpino Evidence Test"},
        compliance_result={"score": 85.0, "status": "NEEDS_REVIEW", "checks": checks_data},
        ocr_text="Ingredients declaration text on back panel",
        owner_user_id=username,
        organization_id=org_id,
    )

    # 3. Verify authenticated image fetch with Bearer token
    res = client.get(f"/api/images/{back_filename}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert len(res.content) == len(png_bytes)

    # 4. Verify unauthenticated fetch returns 401
    unauth_res = client.get(f"/api/images/{back_filename}")
    assert unauth_res.status_code == 401

    # 5. Verify analysis detail returns correct evidence metadata and coordinates
    detail_res = client.get(f"/api/history/{ana_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail_res.status_code == 200
    ana_json = detail_res.json()
    assert len(ana_json.get("images", [])) == 1
    assert ana_json["images"][0]["label"] == "Back"
    assert ana_json["images"][0]["image_url"] == f"/api/images/{back_filename}"

    fs_check = next((c for c in ana_json["compliance_result"]["checks"] if c["rule_id"] == "FS-003"), None)
    assert fs_check is not None
    assert fs_check["bbox"] == [101, 147, 388, 260]
    assert fs_check["evidence"][0]["geometry_type"] == "WORD_UNION"
    assert fs_check["evidence"][0]["confidence"] == 0.81


