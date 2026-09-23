"""
MetrCheck AI — Merchant Product Catalog & Master SKU Management API.

Endpoints:
  POST   /api/products              — Create persistent merchant product record
  GET    /api/products              — List products for authenticated merchant tenant
  GET    /api/products/stats        — Aggregated merchant dashboard KPI metrics
  GET    /api/products/{id}         — Get product details (Tenant & IDOR protected)
  PATCH  /api/products/{id}         — Update editable product metadata
  DELETE /api/products/{id}         — Soft-archive product (preserves historical scans)
  GET    /api/products/{id}/history — Physical scans linked to this product
  GET    /api/products/{id}/artworks— Packaging artworks linked to this product
  GET    /api/products/{id}/summary — Structured product compliance summary
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, status

from auth.security import (
    get_current_user,
    check_tenant_access,
    ROLE_ADMIN,
    ROLE_ENFORCEMENT,
    ROLE_AUDIT,
    ROLE_MERCHANT,
    ROLE_USER,
)
from database.db import (
    create_product,
    get_product,
    list_products,
    update_product,
    archive_product,
    hard_delete_product,
    get_product_analyses,
    get_product_artworks,
    get_product_summary,
    get_merchant_dashboard_metrics,
    log_account_audit_event,
)
from models.product_schemas import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
    ProductHistoryItem,
    ProductArtworkSummary,
    ProductComplianceSummary,
    MerchantDashboardStats,
)

router = APIRouter(prefix="/products", tags=["Merchant Products"])


def _check_merchant_role(user: dict):
    """Guards product catalog endpoints against consumer / normal users."""
    role = user.get("role")
    if role in (ROLE_USER, "NORMAL_USER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Normal consumers cannot access or manage the Merchant Product Catalog."
        )
    if role not in (ROLE_MERCHANT, ROLE_ADMIN, ROLE_ENFORCEMENT, ROLE_AUDIT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Insufficient privileges for merchant product catalog."
        )


@router.post("", response_model=ProductResponse, status_code=201)
async def create_new_product(
    req: ProductCreate,
    user: dict = Depends(get_current_user),
):
    """
    Create a new persistent product master record.
    Security: Server derives organization_id and owner_user_id strictly from authenticated token claims.
    """
    _check_merchant_role(user)

    user_role = user.get("role")
    if user_role not in (ROLE_MERCHANT, ROLE_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only merchants and administrators can create new product catalog entries."
        )

    user_org = (user.get("organization_id") or "").strip()
    if not user_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Merchant account is not assigned to a valid organization tenant."
        )

    product_id = str(uuid.uuid4())
    username = (user.get("username") or "").strip()

    data = {
        "id": product_id,
        "organization_id": user_org,
        "owner_user_id": username,
        "product_name": req.product_name.strip(),
        "brand_name": (req.brand_name or "").strip(),
        "category": (req.category or "GENERAL").strip(),
        "gtin_barcode": (req.gtin_barcode or "").strip(),
        "fssai_license": (req.fssai_license or "").strip(),
        "legal_metrology_license": (req.legal_metrology_license or "").strip(),
        "net_quantity_declared": (req.net_quantity_declared or "").strip(),
        "mrp_declared": float(req.mrp_declared or 0.0),
        "unit_sale_price_declared": (req.unit_sale_price_declared or "").strip(),
        "manufacturer_name": (req.manufacturer_name or "").strip(),
        "country_of_origin": (req.country_of_origin or "India").strip(),
        "status": "ACTIVE",
    }

    created = await create_product(data)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to persist product master record.")

    try:
        await log_account_audit_event(
            actor_username=username,
            target_username=username,
            event_type="PRODUCT_CREATED",
            details=f"Created product SKU '{req.product_name}' (ID: {product_id}) under tenant '{user_org}'",
        )
    except Exception:
        pass

    return ProductResponse(**created)


@router.get("", response_model=ProductListResponse)
async def list_merchant_products(
    search: Optional[str] = Query(None, alias="q", description="Search by name, brand, GTIN"),
    category: Optional[str] = Query(None, description="Filter by category"),
    status_filter: str = Query("ACTIVE", alias="status", description="Filter: ACTIVE | ARCHIVED | ALL"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """
    List products belonging to the authenticated merchant tenant.
    Guarantees strict tenant isolation.
    """
    _check_merchant_role(user)

    user_role = user.get("role")
    user_org = (user.get("organization_id") or "").strip()

    if user_role == ROLE_ADMIN and not user_org:
        # Admin can view across organizations if requested
        user_org = "org_ministry"

    if not user_org:
        return ProductListResponse(products=[], total=0)

    # Scoped strictly to the merchant's tenant
    owner_filter = user.get("username") if user_role == ROLE_MERCHANT else None
    products_raw = await list_products(
        organization_id=user_org,
        owner_user_id=owner_filter,
        status=status_filter,
        search=search,
        category=category,
        limit=limit,
        offset=offset
    )

    items = [ProductResponse(**p) for p in products_raw]
    return ProductListResponse(products=items, total=len(items))


@router.get("/stats", response_model=MerchantDashboardStats)
async def get_merchant_stats_endpoint(
    user: dict = Depends(get_current_user),
):
    """
    Returns live aggregated KPI summary metrics for the Merchant Pre-Flight Dashboard.
    """
    _check_merchant_role(user)

    user_org = (user.get("organization_id") or "").strip()
    if not user_org:
        return MerchantDashboardStats()

    metrics = await get_merchant_dashboard_metrics(
        organization_id=user_org,
        owner_user_id=user.get("username")
    )
    return MerchantDashboardStats(**metrics)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product_endpoint(
    product_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Get product details by ID.
    Enforces tenant access and anti-IDOR validation.
    """
    _check_merchant_role(user)

    product = await get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    check_tenant_access(user, product, raise_exception=True)
    return ProductResponse(**product)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product_endpoint(
    product_id: str,
    req: ProductUpdate,
    user: dict = Depends(get_current_user),
):
    """
    Update editable product metadata.
    Enforces tenant match and record ownership.
    """
    _check_merchant_role(user)

    product = await get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    check_tenant_access(user, product, raise_exception=True)

    update_dict = req.model_dump(exclude_unset=True)
    updated = await update_product(product_id, update_dict)
    if not updated:
        raise HTTPException(status_code=404, detail="Product not found after update.")

    try:
        username = user.get("username", "")
        await log_account_audit_event(
            actor_username=username,
            target_username=username,
            event_type="PRODUCT_UPDATED",
            details=f"Updated product SKU '{updated.get('product_name')}' (ID: {product_id})",
        )
    except Exception:
        pass

    return ProductResponse(**updated)


@router.delete("/{product_id}", response_model=dict)
async def delete_product_endpoint(
    product_id: str,
    hard_delete: bool = Query(False, description="Permanent deletion"),
    user: dict = Depends(get_current_user),
):
    """
    Soft-archive or hard-delete a product record.
    Soft-archive guarantees non-destructive lifecycle: all historical scans, reports, and artworks remain intact.
    """
    _check_merchant_role(user)

    product = await get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    check_tenant_access(user, product, raise_exception=True)

    if hard_delete:
        ok = await hard_delete_product(product_id)
        if not ok:
            raise HTTPException(status_code=400, detail="Could not delete product record.")
        return {"message": "Product deleted successfully.", "id": product_id, "deleted": True}

    ok = await archive_product(product_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Could not archive product record.")

    try:
        username = user.get("username", "")
        await log_account_audit_event(
            actor_username=username,
            target_username=username,
            event_type="PRODUCT_ARCHIVED",
            details=f"Archived product SKU '{product.get('product_name')}' (ID: {product_id})",
        )
    except Exception:
        pass

    return {"message": "Product archived successfully.", "id": product_id, "status": "ARCHIVED"}


@router.get("/{product_id}/history", response_model=dict)
async def get_product_history_endpoint(
    product_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Return physical scan history associated with this product.
    """
    _check_merchant_role(user)

    product = await get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    check_tenant_access(user, product, raise_exception=True)

    analyses = await get_product_analyses(product_id, product["organization_id"])
    results = []
    for a in analyses:
        img_fn = a.get("image_filename") or ""
        results.append(ProductHistoryItem(
            id=a["id"],
            product_name=a.get("product_name") or product.get("product_name", ""),
            image_filename=img_fn,
            image_url=f"/api/images/{img_fn}" if img_fn else None,
            score=float(a.get("score") or 0.0),
            status=a.get("status") or "UNKNOWN",
            created_at=a.get("created_at") or "",
            owner_user_id=a.get("owner_user_id"),
            organization_id=a.get("organization_id"),
            product_id=a.get("product_id"),
            integrity_hash=a.get("integrity_hash")
        ).model_dump())
    return {"product_id": product_id, "analyses": results, "total": len(results)}


@router.get("/{product_id}/artworks", response_model=dict)
async def get_product_artworks_endpoint(
    product_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Return packaging artwork iterations associated with this product.
    """
    _check_merchant_role(user)

    product = await get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    check_tenant_access(user, product, raise_exception=True)

    artworks = await get_product_artworks(product_id, product["organization_id"])
    results = []
    for art in artworks:
        ana_res = art.get("analysis_result") or {}
        overall_score = float(ana_res.get("overall_score", 0.0)) if isinstance(ana_res, dict) and "overall_score" in ana_res else None
        overall_risk = ana_res.get("overall_risk") if isinstance(ana_res, dict) else None

        results.append(ProductArtworkSummary(
            id=art["id"],
            filename=art["filename"],
            file_type=art.get("file_type", "application/pdf"),
            file_size=art.get("file_size", 0),
            page_count=art.get("page_count", 1),
            iteration_number=art.get("iteration_number", 1),
            workflow_status=art.get("workflow_status", "DRAFT"),
            approval_status=art.get("approval_status", "PENDING"),
            created_at=art.get("created_at", ""),
            updated_at=art.get("updated_at", ""),
            product_id=art.get("product_id"),
            overall_score=overall_score,
            overall_risk=overall_risk,
        ).model_dump())
    return {"product_id": product_id, "artworks": results, "total": len(results)}


@router.get("/{product_id}/summary", response_model=ProductComplianceSummary)
async def get_product_summary_endpoint(
    product_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Structured compliance overview including scans count, artwork iterations, and latest score.
    """
    _check_merchant_role(user)

    product = await get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    check_tenant_access(user, product, raise_exception=True)

    summary_data = await get_product_summary(product_id, product["organization_id"])
    if not summary_data:
        raise HTTPException(status_code=404, detail="Summary not available.")

    latest_scan_obj = None
    if summary_data.get("latest_scan"):
        ls = summary_data["latest_scan"]
        img_fn = ls.get("image_filename") or ""
        latest_scan_obj = ProductHistoryItem(
            id=ls["id"],
            product_name=ls.get("product_name") or product.get("product_name", ""),
            image_filename=img_fn,
            image_url=f"/api/images/{img_fn}" if img_fn else None,
            score=float(ls.get("score") or 0.0),
            status=ls.get("status") or "UNKNOWN",
            created_at=ls.get("created_at") or "",
            owner_user_id=ls.get("owner_user_id"),
            organization_id=ls.get("organization_id"),
            product_id=ls.get("product_id"),
            integrity_hash=ls.get("integrity_hash")
        )

    latest_art_obj = None
    if summary_data.get("latest_artwork"):
        la = summary_data["latest_artwork"]
        ana_res = la.get("analysis_result") or {}
        overall_score = float(ana_res.get("overall_score", 0.0)) if isinstance(ana_res, dict) and "overall_score" in ana_res else None
        overall_risk = ana_res.get("overall_risk") if isinstance(ana_res, dict) else None

        latest_art_obj = ProductArtworkSummary(
            id=la["id"],
            filename=la["filename"],
            file_type=la.get("file_type", "application/pdf"),
            file_size=la.get("file_size", 0),
            page_count=la.get("page_count", 1),
            iteration_number=la.get("iteration_number", 1),
            workflow_status=la.get("workflow_status", "DRAFT"),
            approval_status=la.get("approval_status", "PENDING"),
            created_at=la.get("created_at", ""),
            updated_at=la.get("updated_at", ""),
            product_id=la.get("product_id"),
            overall_score=overall_score,
            overall_risk=overall_risk,
        )

    return ProductComplianceSummary(
        product=ProductResponse(**summary_data["product"]),
        total_scans=summary_data["total_scans"],
        total_artworks=summary_data["total_artworks"],
        latest_score=summary_data["latest_score"],
        latest_status=summary_data["latest_status"],
        critical_findings_count=summary_data["critical_findings_count"],
        review_findings_count=summary_data["review_findings_count"],
        latest_scan=latest_scan_obj,
        latest_artwork=latest_art_obj,
    )
