import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Request, status
from pydantic import BaseModel
from typing import List, Optional
import json
from models.schemas import AnalysisResponse
from models.manual_check_schemas import ManualProductCheckRequest
from services.analysis_service import analyze_products, analyze_text, analyze_manual
from utils.validators import validate_image_file
from auth.security import public_user, check_tenant_access, require_roles, ROLE_USER, ROLE_ADMIN
from auth.ratelimit import get_client_ip, check_analysis_rate_limit
from database.db import get_product

logger = logging.getLogger(__name__)


router = APIRouter()

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_endpoint(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    labels: Optional[str] = Form(None),
    product_id: Optional[str] = Form(None),
    user: Optional[dict] = Depends(public_user)
):
    client_ip = get_client_ip(request)
    allowed, rate_msg = check_analysis_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    upload_list: List[UploadFile] = []
    if files:
        upload_list.extend(files)
    if file and file not in upload_list:
        upload_list.append(file)
        
    if not upload_list:
        raise HTTPException(status_code=400, detail="At least one image file is required for analysis.")
        
    for f in upload_list:
        validate_image_file(f)
        
    parsed_labels: Optional[List[str]] = None
    if labels:
        try:
            parsed = json.loads(labels)
            if isinstance(parsed, list):
                parsed_labels = [str(l).strip() for l in parsed]
        except Exception:
            parsed_labels = [l.strip() for l in labels.split(',') if l.strip()]
            
    owner_user_id = user.get("username", "") if user else ""
    organization_id = user.get("organization_id", "") if user else ""

    validated_product_id: Optional[str] = None
    if product_id and product_id.strip():
        clean_pid = product_id.strip()
        product = await get_product(clean_pid)
        if not product:
            raise HTTPException(status_code=404, detail="Specified product was not found.")
        check_tenant_access(user, product, raise_exception=True)
        validated_product_id = clean_pid

    try:
        result = await analyze_products(
            upload_list,
            parsed_labels,
            owner_user_id=owner_user_id,
            organization_id=organization_id,
            product_id=validated_product_id
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Image analysis failed for request: %s", e)
        raise HTTPException(status_code=500, detail="An internal server error occurred during analysis.")


class TextAnalyzeRequest(BaseModel):
    text: str
    product_id: Optional[str] = None


@router.post("/analyze/text", response_model=AnalysisResponse)
async def analyze_text_endpoint(
    req: TextAnalyzeRequest,
    request: Request,
    user: Optional[dict] = Depends(public_user)
):
    client_ip = get_client_ip(request)
    allowed, rate_msg = check_analysis_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text is required for analysis.")
    owner_user_id = user.get("username", "") if user else ""
    organization_id = user.get("organization_id", "") if user else ""

    validated_product_id: Optional[str] = None
    if req.product_id and req.product_id.strip():
        clean_pid = req.product_id.strip()
        product = await get_product(clean_pid)
        if not product:
            raise HTTPException(status_code=404, detail="Specified product was not found.")
        check_tenant_access(user, product, raise_exception=True)
        validated_product_id = clean_pid

    try:
        result = await analyze_text(
            req.text.strip(),
            owner_user_id=owner_user_id,
            organization_id=organization_id,
            product_id=validated_product_id
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Text analysis failed for request: %s", e)
        raise HTTPException(status_code=500, detail="An internal server error occurred during analysis.")


@router.post("/analyze/manual", response_model=AnalysisResponse)
async def analyze_manual_endpoint(
    req: ManualProductCheckRequest,
    request: Request,
    user: dict = Depends(require_roles(ROLE_USER, "NORMAL_USER", "USER", ROLE_ADMIN))
):
    """Consumer Manual Product Check endpoint (NU-06). Restricted to PUBLIC_USER / NORMAL_USER / USER / ADMIN."""
    client_ip = get_client_ip(request)
    allowed, rate_msg = check_analysis_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_msg,
        )

    if not req.product_name or not req.product_name.strip():
        raise HTTPException(status_code=400, detail="Product / Commodity Name is required for manual screening.")
        
    owner_user_id = user.get("username", "")
    organization_id = user.get("organization_id", "")

    try:
        result = await analyze_manual(
            req,
            owner_user_id=owner_user_id,
            organization_id=organization_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Manual product analysis failed for request: %s", e)
        raise HTTPException(status_code=500, detail="An internal server error occurred during manual compliance analysis.")



