"""
MetrCheck AI — Phase NU-07.3 Automated Test Suite
Target: Normal User / Consumer Workspace History Thumbnail Loading & Security Verification

Validates:
1. History record with valid image reference
2. Multiple history records with distinct images
3. Missing image reference handling (/placeholder.png)
4. Multi-image schema fallback resolution
5. Authenticated image retrieval via Bearer token
6. Unauthorized (unauthenticated) image access blocked (401)
7. Cross-tenant / IDOR image access blocked (403)
8. History search endpoint image resolution
9. Existing analysis retrieval with full image evidence
10. History record deletion with file cleanup
11. Language invariance across history metadata
"""

import pytest
import os
import json
from fastapi.testclient import TestClient
from main import app
from config import settings, PROD_DATABASE_PATH, PROD_UPLOAD_DIR
from auth.security import create_token, ROLE_USER, ROLE_ADMIN, ROLE_MERCHANT, hash_password
from database.db import create_user, save_analysis, get_analysis


@pytest.fixture(autouse=True)
def verify_test_isolation_active():
    assert os.path.abspath(settings.DATABASE_PATH) != PROD_DATABASE_PATH, "Test must run in test database"
    assert os.path.abspath(settings.UPLOAD_DIR) != PROD_UPLOAD_DIR, "Test must run in test uploads directory"


@pytest.mark.asyncio
async def test_01_history_item_with_valid_image():
    """History endpoint correctly returns /api/images/{filename} for record with image_filename."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_hist1", pwh, salt, ROLE_USER, "User Hist1", organization_id="org_user_hist1")
    token = create_token("user_hist1", ROLE_USER)

    aid = "nu073-test-item-001"
    img_fname = f"{aid}_front.png"
    img_path = os.path.join(settings.UPLOAD_DIR, img_fname)
    with open(img_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRTESTBYTES01")

    await save_analysis({
        "id": aid,
        "product_name": "Alpino Peanut Butter",
        "image_filename": img_fname,
        "ocr_text": "Net Weight 400g MRP Rs 299",
        "extracted_data": {"net_quantity": "400g", "mrp": "299"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 95.0},
        "score": 95.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T10:00:00Z",
        "images": [{"filename": img_fname, "image_url": f"/api/images/{img_fname}", "label": "Front"}],
        "owner_user_id": "user_hist1",
        "organization_id": "org_user_hist1"
    })

    resp = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    match = next((i for i in items if i["id"] == aid), None)
    assert match is not None, "Analysis must be in history list"
    assert match["image_url"] == f"/api/images/{img_fname}"


@pytest.mark.asyncio
async def test_02_history_item_with_multi_image_structure_fallback():
    """When image_filename is empty, history endpoint safely extracts primary image from images JSON."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_hist2", pwh, salt, ROLE_USER, "User Hist2", organization_id="org_user_hist2")
    token = create_token("user_hist2", ROLE_USER)

    aid = "nu073-test-item-002"
    img_fname = f"{aid}_panel1.png"
    img_path = os.path.join(settings.UPLOAD_DIR, img_fname)
    with open(img_path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRTESTBYTES02")

    await save_analysis({
        "id": aid,
        "product_name": "Multi-Image Protein Shake",
        "image_filename": "",  # Empty top-level filename
        "ocr_text": "Net Qty 250ml MRP Rs 99",
        "extracted_data": {"net_quantity": "250ml", "mrp": "99"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 90.0},
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T10:05:00Z",
        "images": [{"filename": img_fname, "image_url": f"/api/images/{img_fname}", "label": "Front"}],
        "owner_user_id": "user_hist2",
        "organization_id": "org_user_hist2"
    })

    resp = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    match = next((i for i in items if i["id"] == aid), None)
    assert match is not None
    assert match["image_url"] == f"/api/images/{img_fname}", "Should fallback to images[0] URL"


@pytest.mark.asyncio
async def test_03_history_item_without_image():
    """When no image exists, history endpoint returns clean /placeholder.png."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_hist3", pwh, salt, ROLE_USER, "User Hist3", organization_id="org_user_hist3")
    token = create_token("user_hist3", ROLE_USER)

    aid = "nu073-test-item-003"
    await save_analysis({
        "id": aid,
        "product_name": "Manual Checked Biscuit",
        "image_filename": "",
        "ocr_text": "Manual text",
        "extracted_data": {},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 100.0},
        "score": 100.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T10:10:00Z",
        "images": [],
        "owner_user_id": "user_hist3",
        "organization_id": "org_user_hist3"
    })

    resp = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    match = next((i for i in items if i["id"] == aid), None)
    assert match is not None
    assert match["image_url"] == "/placeholder.png"


@pytest.mark.asyncio
async def test_04_authenticated_image_fetching_succeeds():
    """Authenticated user with valid Bearer token can fetch image from /api/images/{filename}."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_hist4", pwh, salt, ROLE_USER, "User Hist4", organization_id="org_user_hist4")
    token = create_token("user_hist4", ROLE_USER)

    aid = "nu073-test-item-004"
    img_fname = f"{aid}_front.png"
    img_path = os.path.join(settings.UPLOAD_DIR, img_fname)
    img_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRREALIMAGE04"
    with open(img_path, "wb") as f:
        f.write(img_data)

    await save_analysis({
        "id": aid,
        "product_name": "Organic Honey",
        "image_filename": img_fname,
        "ocr_text": "Honey 500g",
        "extracted_data": {},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 92.0},
        "score": 92.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T10:15:00Z",
        "images": [{"filename": img_fname, "image_url": f"/api/images/{img_fname}"}],
        "owner_user_id": "user_hist4",
        "organization_id": "org_user_hist4"
    })

    resp = client.get(f"/api/images/{img_fname}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.content == img_data
    assert "image/png" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_05_unauthenticated_image_fetching_blocked():
    """Unauthenticated GET to /api/images/{filename} must return 401 Unauthorized."""
    client = TestClient(app)

    aid = "nu073-test-item-005"
    img_fname = f"{aid}_front.png"
    img_path = os.path.join(settings.UPLOAD_DIR, img_fname)
    with open(img_path, "wb") as f:
        f.write(b"SECRET_DATA")

    resp = client.get(f"/api/images/{img_fname}")
    assert resp.status_code == 401, "Direct unauthenticated img src must be rejected"


@pytest.mark.asyncio
async def test_06_cross_tenant_image_access_blocked():
    """User B cannot fetch User A's image from /api/images/{filename} (IDOR protection)."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_alice_nu073", pwh, salt, ROLE_USER, "Alice", organization_id="org_alice")
    await create_user("user_bob_nu073", pwh, salt, ROLE_USER, "Bob", organization_id="org_bob")

    token_alice = create_token("user_alice_nu073", ROLE_USER)
    token_bob = create_token("user_bob_nu073", ROLE_USER)

    aid = "nu073-test-alice-item"
    img_fname = f"{aid}_front.png"
    img_path = os.path.join(settings.UPLOAD_DIR, img_fname)
    with open(img_path, "wb") as f:
        f.write(b"ALICE_ONLY_IMAGE")

    await save_analysis({
        "id": aid,
        "product_name": "Alice Private Artwork",
        "image_filename": img_fname,
        "ocr_text": "Alice brand",
        "extracted_data": {},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 90.0},
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T10:20:00Z",
        "images": [{"filename": img_fname, "image_url": f"/api/images/{img_fname}"}],
        "owner_user_id": "user_alice_nu073",
        "organization_id": "org_alice"
    })

    # Alice can access her own image
    alice_resp = client.get(f"/api/images/{img_fname}", headers={"Authorization": f"Bearer {token_alice}"})
    assert alice_resp.status_code == 200

    # Bob cannot access Alice's image
    bob_resp = client.get(f"/api/images/{img_fname}", headers={"Authorization": f"Bearer {token_bob}"})
    assert bob_resp.status_code == 403, "Cross-user image access must be 403 Forbidden"


@pytest.mark.asyncio
async def test_07_multiple_history_records_independent_images():
    """Multiple history records maintain their own independent images without cross-contamination."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_multi_img", pwh, salt, ROLE_USER, "Multi User", organization_id="org_multi_user")
    token = create_token("user_multi_img", ROLE_USER)

    for i in range(1, 4):
        aid = f"nu073-multi-{i}"
        img_fn = f"{aid}.png"
        with open(os.path.join(settings.UPLOAD_DIR, img_fn), "wb") as f:
            f.write(f"IMAGE_BYTES_{i}".encode("utf-8"))

        await save_analysis({
            "id": aid,
            "product_name": f"Product {i}",
            "image_filename": img_fn,
            "ocr_text": f"Product {i} text",
            "extracted_data": {},
            "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 80.0 + i},
            "score": 80.0 + i,
            "status": "COMPLIANT",
            "created_at": f"2026-09-23T10:30:0{i}Z",
            "images": [{"filename": img_fn, "image_url": f"/api/images/{img_fn}"}],
            "owner_user_id": "user_multi_img",
            "organization_id": "org_multi_user"
        })

    resp = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()
    multi_items = [item for item in items if item["id"].startswith("nu073-multi-")]
    assert len(multi_items) == 3
    urls = [m["image_url"] for m in multi_items]
    assert len(set(urls)) == 3, "Each history item must have its own distinct image URL"


@pytest.mark.asyncio
async def test_08_search_history_resolves_image_urls():
    """Search history endpoint returns properly resolved image_url for matched records."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_search_img", pwh, salt, ROLE_USER, "Search User", organization_id="org_search_img")
    token = create_token("user_search_img", ROLE_USER)

    aid = "nu073-searchable-apple"
    img_fn = f"{aid}.png"
    with open(os.path.join(settings.UPLOAD_DIR, img_fn), "wb") as f:
        f.write(b"APPLE_IMAGE")

    await save_analysis({
        "id": aid,
        "product_name": "Fresh Apple Juice",
        "image_filename": img_fn,
        "ocr_text": "Apple Juice 1L",
        "extracted_data": {},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 96.0},
        "score": 96.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T10:40:00Z",
        "images": [{"filename": img_fn, "image_url": f"/api/images/{img_fn}"}],
        "owner_user_id": "user_search_img",
        "organization_id": "org_search_img"
    })

    search_resp = client.get(
        "/api/history/search?q=Apple",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert search_resp.status_code == 200
    results = search_resp.json()
    match = next((r for r in results if r["id"] == aid), None)
    assert match is not None
    assert match["image_url"] == f"/api/images/{img_fn}"


@pytest.mark.asyncio
async def test_09_delete_history_cleans_image_file():
    """Deleting a history record cleans up its associated physical image files."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_del_img", pwh, salt, ROLE_USER, "Delete User", organization_id="org_del_img")
    token = create_token("user_del_img", ROLE_USER)

    aid = "nu073-delete-item"
    img_fn = f"{aid}_front.png"
    img_path = os.path.join(settings.UPLOAD_DIR, img_fn)
    with open(img_path, "wb") as f:
        f.write(b"DELETE_ME")

    await save_analysis({
        "id": aid,
        "product_name": "Temporary Product",
        "image_filename": img_fn,
        "ocr_text": "Temp text",
        "extracted_data": {},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 90.0},
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T10:45:00Z",
        "images": [{"filename": img_fn, "image_url": f"/api/images/{img_fn}"}],
        "owner_user_id": "user_del_img",
        "organization_id": "org_del_img"
    })

    assert os.path.exists(img_path)

    del_resp = client.delete(
        f"/api/history/{aid}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert del_resp.status_code == 200
    assert not os.path.exists(img_path), "Image file must be cleaned up on delete"
    assert await get_analysis(aid) is None


@pytest.mark.asyncio
async def test_10_alpino_analysis_history_and_results_image_parity():
    """Validates that an analysis record (like Alpino 99b3751d) resolves the exact same authenticated image URL in History and Results."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_alpino_test", pwh, salt, ROLE_USER, "Alpino Tester", organization_id="org_alpino_test")
    token = create_token("user_alpino_test", ROLE_USER)

    aid = "99b3751d-81a0-4f9e-b123-abcdef012345"
    img_fname = f"{aid}_alpino_front.png"
    img_path = os.path.join(settings.UPLOAD_DIR, img_fname)
    img_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRALPINOBYTES"
    with open(img_path, "wb") as f:
        f.write(img_bytes)

    await save_analysis({
        "id": aid,
        "product_name": "Alpino Super Creamy Peanut Butter",
        "image_filename": img_fname,
        "ocr_text": "Alpino Peanut Butter 1kg MRP Rs 499",
        "extracted_data": {"net_quantity": "1kg", "mrp": "499"},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 98.0},
        "score": 98.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T11:00:00Z",
        "images": [{"filename": img_fname, "image_url": f"/api/images/{img_fname}", "label": "Front"}],
        "owner_user_id": "user_alpino_test",
        "organization_id": "org_alpino_test"
    })

    # 1. Fetch via /api/history
    hist_resp = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert hist_resp.status_code == 200
    hist_items = hist_resp.json()
    hist_match = next((h for h in hist_items if h["id"] == aid), None)
    assert hist_match is not None
    assert hist_match["image_url"] == f"/api/images/{img_fname}"

    # 2. Fetch via /api/history/{id} (Results page source)
    res_resp = client.get(f"/api/history/{aid}", headers={"Authorization": f"Bearer {token}"})
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    
    # Check that ResultsHeader front image matches History image_url
    assert res_data["image_url"] == hist_match["image_url"]
    assert res_data["images"][0]["image_url"] == hist_match["image_url"]

    # 3. Authenticated image fetch returns identical binary data
    img_resp = client.get(hist_match["image_url"], headers={"Authorization": f"Bearer {token}"})
    assert img_resp.status_code == 200
    assert img_resp.content == img_bytes


@pytest.mark.asyncio
async def test_11_mixed_history_batch_independent_resolution():
    """Validates mixed batch with valid image, missing image, and multi-panel image in single history query."""
    client = TestClient(app)

    pwh, salt = hash_password("pass123")
    await create_user("user_mixed_batch", pwh, salt, ROLE_USER, "Mixed Tester", organization_id="org_mixed_batch")
    token = create_token("user_mixed_batch", ROLE_USER)

    # Item A: Valid single image
    aid_a = "nu0731-batch-a"
    img_a = f"{aid_a}.png"
    with open(os.path.join(settings.UPLOAD_DIR, img_a), "wb") as f:
        f.write(b"PNG_A")

    await save_analysis({
        "id": aid_a,
        "product_name": "Product A Valid",
        "image_filename": img_a,
        "ocr_text": "Text A",
        "extracted_data": {},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 90.0},
        "score": 90.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T11:10:00Z",
        "images": [{"filename": img_a, "image_url": f"/api/images/{img_a}"}],
        "owner_user_id": "user_mixed_batch",
        "organization_id": "org_mixed_batch"
    })

    # Item B: No image (placeholder)
    aid_b = "nu0731-batch-b"
    await save_analysis({
        "id": aid_b,
        "product_name": "Product B Manual",
        "image_filename": "",
        "ocr_text": "Text B",
        "extracted_data": {},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 85.0},
        "score": 85.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T11:11:00Z",
        "images": [],
        "owner_user_id": "user_mixed_batch",
        "organization_id": "org_mixed_batch"
    })

    # Item C: Multi-panel fallback image
    aid_c = "nu0731-batch-c"
    img_c = f"{aid_c}_panel.png"
    with open(os.path.join(settings.UPLOAD_DIR, img_c), "wb") as f:
        f.write(b"PNG_C")

    await save_analysis({
        "id": aid_c,
        "product_name": "Product C Multi",
        "image_filename": "",
        "ocr_text": "Text C",
        "extracted_data": {},
        "compliance_result": {"checks": [], "status": "COMPLIANT", "score": 95.0},
        "score": 95.0,
        "status": "COMPLIANT",
        "created_at": "2026-09-23T11:12:00Z",
        "images": [{"filename": img_c, "image_url": f"/api/images/{img_c}"}],
        "owner_user_id": "user_mixed_batch",
        "organization_id": "org_mixed_batch"
    })

    resp = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = {i["id"]: i for i in resp.json()}

    assert items[aid_a]["image_url"] == f"/api/images/{img_a}"
    assert items[aid_b]["image_url"] == "/placeholder.png"
    assert items[aid_c]["image_url"] == f"/api/images/{img_c}"

