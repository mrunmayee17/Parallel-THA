"""Insurance Item Matcher - A service for matching lost items to online products."""

from .insurance_item_matcher import InsuranceItemMatcher
from .models import Product, ItemDescription, SearchResult, APIError, ValidationError
from .config import Config

__version__ = "1.0.0"
__author__ = "Insurance Item Matcher Team"
__description__ = "Find online product matches for lost/stolen items to determine insurance reimbursement values"

__all__ = [
    "InsuranceItemMatcher",
    "Product", 
    "ItemDescription", 
    "SearchResult",
    "APIError",
    "ValidationError", 
    "Config"
]