"""Data models for the Insurance Item Matcher service."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl, Field, validator
from decimal import Decimal


class Product(BaseModel):
    """Represents a matched product."""
    
    name: str = Field(..., description="Product name")
    price: Optional[Decimal] = Field(None, description="Product price")
    currency: str = Field(default="USD", description="Price currency")
    url: Optional[HttpUrl] = Field(None, description="Direct product URL")
    description: Optional[str] = Field(None, description="Product description")
    brand: Optional[str] = Field(None, description="Product brand")
    model: Optional[str] = Field(None, description="Product model")
    condition: Optional[str] = Field(default="new", description="Product condition")
    availability: Optional[str] = Field(None, description="Product availability")
    source: Optional[str] = Field(None, description="Source website/retailer")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Match confidence score")
    
    @validator('price', pre=True)
    def validate_price(cls, v):
        """Validate and convert price to Decimal."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            # Remove currency symbols and convert
            price_str = v.replace('$', '').replace(',', '').strip()
            try:
                return Decimal(price_str)
            except:
                return None
        return v


class ItemDescription(BaseModel):
    """Represents an item description for matching."""
    
    text: str = Field(..., description="Original item description")
    category: Optional[str] = Field(None, description="Inferred item category")
    brand: Optional[str] = Field(None, description="Extracted brand")
    model: Optional[str] = Field(None, description="Extracted model")
    specifications: Dict[str, str] = Field(default_factory=dict, description="Extracted specifications")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")


class SearchResult(BaseModel):
    """Represents the complete search result."""
    
    query: ItemDescription = Field(..., description="Original item description")
    matched_products: List[Product] = Field(default_factory=list, description="List of matched products")
    search_metadata: Dict[str, Any] = Field(default_factory=dict, description="Search metadata")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    total_results: int = Field(default=0, description="Total number of results found")
    
    @validator('matched_products')
    def sort_by_confidence(cls, v):
        """Sort products by confidence score descending."""
        return sorted(v, key=lambda x: x.confidence_score or 0, reverse=True)


class APIError(Exception):
    """Custom exception for API-related errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass