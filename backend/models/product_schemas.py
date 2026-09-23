from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """Payload for creating a persistent merchant product record."""
    product_name: str = Field(min_length=1, max_length=200, description="Product Name / SKU Title")
    brand_name: Optional[str] = Field(default="", max_length=100)
    category: Optional[str] = Field(default="GENERAL", max_length=50)
    gtin_barcode: Optional[str] = Field(default="", max_length=50)
    fssai_license: Optional[str] = Field(default="", max_length=50)
    legal_metrology_license: Optional[str] = Field(default="", max_length=50)
    net_quantity_declared: Optional[str] = Field(default="", max_length=100)
    mrp_declared: Optional[float] = Field(default=0.0, ge=0.0)
    unit_sale_price_declared: Optional[str] = Field(default="", max_length=100)
    manufacturer_name: Optional[str] = Field(default="", max_length=200)
    country_of_origin: Optional[str] = Field(default="India", max_length=100)


class ProductUpdate(BaseModel):
    """Payload for updating editable merchant product metadata."""
    product_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    brand_name: Optional[str] = Field(default=None, max_length=100)
    category: Optional[str] = Field(default=None, max_length=50)
    gtin_barcode: Optional[str] = Field(default=None, max_length=50)
    fssai_license: Optional[str] = Field(default=None, max_length=50)
    legal_metrology_license: Optional[str] = Field(default=None, max_length=50)
    net_quantity_declared: Optional[str] = Field(default=None, max_length=100)
    mrp_declared: Optional[float] = Field(default=None, ge=0.0)
    unit_sale_price_declared: Optional[str] = Field(default=None, max_length=100)
    manufacturer_name: Optional[str] = Field(default=None, max_length=200)
    country_of_origin: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(default=None, max_length=20)


class ProductResponse(BaseModel):
    """Product master record output model."""
    id: str
    organization_id: str
    owner_user_id: str
    product_name: str
    brand_name: str = ""
    category: str = "GENERAL"
    gtin_barcode: str = ""
    fssai_license: str = ""
    legal_metrology_license: str = ""
    net_quantity_declared: str = ""
    mrp_declared: float = 0.0
    unit_sale_price_declared: str = ""
    manufacturer_name: str = ""
    country_of_origin: str = "India"
    status: str = "ACTIVE"
    created_at: str
    updated_at: str


class ProductListResponse(BaseModel):
    """List of merchant products."""
    products: List[ProductResponse]
    total: int


class ProductHistoryItem(BaseModel):
    """Product-associated physical scan summary."""
    id: str
    product_name: str
    image_filename: Optional[str] = None
    image_url: Optional[str] = None
    score: float = 0.0
    status: str = "UNKNOWN"
    created_at: str
    owner_user_id: Optional[str] = None
    organization_id: Optional[str] = None
    product_id: Optional[str] = None
    integrity_hash: Optional[str] = None


class ProductArtworkSummary(BaseModel):
    """Product-associated packaging artwork summary."""
    id: str
    filename: str
    file_type: str
    file_size: int
    page_count: int = 1
    iteration_number: int = 1
    workflow_status: str = "DRAFT"
    approval_status: str = "PENDING"
    created_at: str
    updated_at: str
    product_id: Optional[str] = None
    overall_score: Optional[float] = None
    overall_risk: Optional[str] = None


class ProductComplianceSummary(BaseModel):
    """Structured compliance overview for a product master record."""
    product: ProductResponse
    total_scans: int = 0
    total_artworks: int = 0
    latest_score: float = 0.0
    latest_status: str = "NOT_SCREENED"
    critical_findings_count: int = 0
    review_findings_count: int = 0
    latest_scan: Optional[ProductHistoryItem] = None
    latest_artwork: Optional[ProductArtworkSummary] = None


class MerchantDashboardStats(BaseModel):
    """KPI summary counters for the Merchant Business Dashboard."""
    active_products: int = 0
    products_checked: int = 0
    attention_required: int = 0
    critical_findings: int = 0
    packaging_artworks: int = 0
