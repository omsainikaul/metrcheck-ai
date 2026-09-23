import logging
from fastapi import APIRouter
from ocr.factory import get_ocr_engine
from version import SYSTEM_VERSION

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint. Returns live system status.
    - ocr_available: actual check against the OCR engine instance
    - database: lightweight real connectivity check (SELECT 1)
    - version: from version.py SYSTEM_VERSION (authoritative)
    """
    ocr_engine = get_ocr_engine()

    # Lightweight real database connectivity check
    db_status = "disconnected"
    try:
        from database.db import get_db
        from config import settings
        import aiosqlite
        db = await aiosqlite.connect(settings.DATABASE_PATH)
        await db.execute("SELECT 1")
        await db.close()
        db_status = "connected"
    except Exception as exc:
        logger.warning("Health check: database connectivity test failed: %s", exc)
        db_status = "disconnected"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "ocr_available": ocr_engine.is_available(),
        "ocr_engine": ocr_engine.__class__.__name__,
        "database": db_status,
        "version": SYSTEM_VERSION,
    }
