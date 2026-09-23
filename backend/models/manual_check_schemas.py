"""
NU-06: Consumer Manual Product Check Request Schema
Minimal, focused declaration model for consumer manual compliance checks.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ManualProductCheckRequest(BaseModel):
    product_type: str = Field(default="FOOD", description="FOOD or NON_FOOD")
    product_name: str = Field(..., min_length=1, description="Common or generic name / product name (required)")
    brand: Optional[str] = None

    @field_validator("product_name")
    @classmethod
    def validate_product_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Product / Commodity Name cannot be empty or whitespace.")
        return v.strip()
    generic_name: Optional[str] = None
    category: Optional[str] = None
    
    # Quantity & Pricing
    net_quantity: Optional[str] = None
    mrp: Optional[str] = None
    unit_sale_price: Optional[str] = None
    
    # Dates
    manufacture_date: Optional[str] = None
    expiry_date: Optional[str] = None
    best_before: Optional[str] = None
    
    # Manufacturer / Packer
    manufacturer_name: Optional[str] = None
    manufacturer_address: Optional[str] = None
    packer_name: Optional[str] = None
    packer_address: Optional[str] = None
    
    # Other Declarations
    batch_number: Optional[str] = None
    country_of_origin: Optional[str] = "India"
    consumer_care_phone: Optional[str] = None
    consumer_care_email: Optional[str] = None
    consumer_care_address: Optional[str] = None
    
    # Food-specific Declarations
    fssai_license: Optional[str] = None
    ingredients: Optional[str] = None
    allergen_info: Optional[str] = None
    nutritional_info: Optional[str] = None
