from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from models.schemas import (
    ScoringConfiguration,
    ProductRiskHistory,
    BatchRiskDistribution,
    ScoreHistoryEntry
)
from compliance.scorer import get_scoring_config, set_scoring_config
from database.db import (
    get_analysis,
    get_product_risk_history,
    get_batch_risk_distribution,
    _extract_analysis_risk_info
)
import json

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.get("/config", response_model=ScoringConfiguration)
async def get_configuration():
    """Retrieve the current active scoring weights and risk thresholds."""
    return get_scoring_config()


@router.put("/config", response_model=ScoringConfiguration)
async def update_configuration(new_config: ScoringConfiguration):
    """Update active scoring weights and risk thresholds."""
    return set_scoring_config(new_config)


@router.get("/history/{analysis_id}", response_model=ScoreHistoryEntry)
async def get_analysis_score_history(analysis_id: str):
    """Retrieve scoring breakdown and risk tier for a specific analysis record."""
    analysis = await get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found.")
    
    info = _extract_analysis_risk_info(analysis)
    return ScoreHistoryEntry(**info)


@router.get("/product/{product_name}/history", response_model=ProductRiskHistory)
async def get_product_history(product_name: str):
    """Retrieve historical compliance scores and risk trajectory for a product."""
    data = await get_product_risk_history(product_name)
    return ProductRiskHistory(**data)


@router.get("/batch-distribution", response_model=BatchRiskDistribution)
async def get_batch_distribution(owner_user_id: Optional[str] = Query(None, description="Optional owner filter")):
    """Retrieve aggregated batch risk level distribution."""
    data = await get_batch_risk_distribution(owner_user_id=owner_user_id)
    return BatchRiskDistribution(**data)
