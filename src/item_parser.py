"""Item description parser and query generator for the Insurance Item Matcher."""

import re
import logging
from typing import List, Dict, Optional, Tuple
from .models import ItemDescription


logger = logging.getLogger(__name__)


class ItemDescriptionParser:
    """Parses item descriptions and generates search queries."""
    
    # Common brand patterns
    BRAND_PATTERNS = {
        'electronics': [
            'apple', 'samsung', 'google', 'microsoft', 'sony', 'lg', 'dell', 'hp', 'lenovo',
            'asus', 'acer', 'nintendo', 'xbox', 'playstation', 'canon', 'nikon', 'panasonic',
            'bose', 'beats', 'jbl', 'sennheiser', 'fitbit', 'garmin', 'gopro'
        ],
        'furniture': [
            'ikea', 'ashley', 'wayfair', 'west elm', 'pottery barn', 'crate and barrel',
            'restoration hardware', 'cb2', 'pier 1', 'rooms to go', 'la-z-boy'
        ],
        'clothing': [
            'nike', 'adidas', 'gucci', 'prada', 'louis vuitton', 'chanel', 'versace',
            'calvin klein', 'tommy hilfiger', 'ralph lauren', 'gap', 'zara', 'h&m'
        ],
        'automotive': [
            'toyota', 'honda', 'ford', 'chevrolet', 'bmw', 'mercedes', 'audi', 'nissan',
            'hyundai', 'kia', 'volkswagen', 'subaru', 'mazda', 'lexus', 'acura'
        ]
    }
    
    # Category indicators
    CATEGORY_KEYWORDS = {
        'electronics': [
            'phone', 'iphone', 'android', 'smartphone', 'tablet', 'ipad', 'laptop', 'computer',
            'tv', 'television', 'monitor', 'headphones', 'earbuds', 'speaker', 'camera',
            'gaming', 'console', 'smartwatch', 'fitness tracker'
        ],
        'furniture': [
            'couch', 'sofa', 'chair', 'table', 'desk', 'bed', 'mattress', 'dresser',
            'bookshelf', 'cabinet', 'nightstand', 'ottoman', 'sectional', 'recliner'
        ],
        'clothing': [
            'shirt', 'pants', 'dress', 'jacket', 'coat', 'shoes', 'sneakers', 'boots',
            'jeans', 'sweater', 'hoodie', 'suit', 'skirt', 'blouse', 'top'
        ],
        'jewelry': [
            'ring', 'necklace', 'bracelet', 'earrings', 'watch', 'chain', 'pendant',
            'diamond', 'gold', 'silver', 'platinum', 'jewelry'
        ],
        'automotive': [
            'car', 'truck', 'suv', 'sedan', 'coupe', 'convertible', 'motorcycle',
            'vehicle', 'auto', 'wheels', 'tires'
        ],
        'appliances': [
            'refrigerator', 'washer', 'dryer', 'dishwasher', 'oven', 'microwave',
            'vacuum', 'blender', 'toaster', 'coffee maker', 'air conditioner'
        ]
    }
    
    # Model/specification patterns
    MODEL_PATTERNS = [
        r'(?:model|mod)\.?\s*([A-Z0-9\-]+)',
        r'([A-Z]{1,3}[0-9]{2,}[A-Z0-9]*)',  # e.g., XYZ123, A1B2C3
        r'(\b[0-9]{3,}[A-Z]{0,3}\b)',        # e.g., 123ABC, 456
        r'([A-Z][0-9]+\s*(?:Pro|Max|Plus|Mini|Air|Ultra)?)',  # iPhone patterns
        r'(Generation\s+[0-9]+|Gen\s*[0-9]+)',  # Generation indicators
    ]
    
    # Size/specification patterns
    SIZE_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*(inch|"|in|ft|feet|cm|mm|meter)',
        r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)',  # dimensions
        r'(\d+(?:GB|TB|MB))',  # storage
        r'(\d+(?:hz|Hz|mhz|MHz|ghz|GHz))',  # frequency
    ]
    
    def parse_description(self, description: str) -> ItemDescription:
        """Parse an item description into structured components.
        
        Args:
            description: Raw item description text
            
        Returns:
            Parsed ItemDescription object
        """
        logger.debug(f"Parsing description: {description}")
        
        # Clean and normalize the description
        clean_desc = self._clean_description(description)
        
        # Extract components
        category = self._extract_category(clean_desc)
        brand = self._extract_brand(clean_desc, category)
        model = self._extract_model(clean_desc)
        specifications = self._extract_specifications(clean_desc)
        keywords = self._extract_keywords(clean_desc)
        
        return ItemDescription(
            text=description,
            category=category,
            brand=brand,
            model=model,
            specifications=specifications,
            keywords=keywords
        )
    
    def generate_search_queries(self, item_desc: ItemDescription) -> List[str]:
        """Generate search queries for finding matching products.
        
        Args:
            item_desc: Parsed item description
            
        Returns:
            List of search queries ordered by specificity
        """
        queries = []
        
        # Most specific query: brand + model + category
        if item_desc.brand and item_desc.model and item_desc.category:
            queries.append(f"{item_desc.brand} {item_desc.model} {item_desc.category}")
        
        # Brand + model
        if item_desc.brand and item_desc.model:
            queries.append(f"{item_desc.brand} {item_desc.model}")
        
        # Brand + category + key specifications
        if item_desc.brand and item_desc.category:
            spec_str = " ".join([f"{k} {v}" for k, v in item_desc.specifications.items()][:2])
            if spec_str:
                queries.append(f"{item_desc.brand} {item_desc.category} {spec_str}")
            else:
                queries.append(f"{item_desc.brand} {item_desc.category}")
        
        # Category + key specifications
        if item_desc.category:
            spec_str = " ".join([f"{k} {v}" for k, v in item_desc.specifications.items()][:3])
            if spec_str:
                queries.append(f"{item_desc.category} {spec_str}")
        
        # Keywords-based query
        if item_desc.keywords:
            keyword_query = " ".join(item_desc.keywords[:5])  # Top 5 keywords
            queries.append(keyword_query)
        
        # Fallback: original description (truncated if too long)
        original = item_desc.text
        if len(original) > 100:
            original = original[:100] + "..."
        queries.append(original)
        
        # Remove duplicates while preserving order
        unique_queries = []
        for query in queries:
            if query and query not in unique_queries:
                unique_queries.append(query)
        
        logger.debug(f"Generated queries: {unique_queries}")
        return unique_queries
    
    def _clean_description(self, description: str) -> str:
        """Clean and normalize description text."""
        # Remove extra whitespace and normalize case
        clean = re.sub(r'\s+', ' ', description.strip().lower())
        
        # Remove common prefixes/suffixes
        clean = re.sub(r'^(lost|stolen|missing|broken)\s+', '', clean)
        clean = re.sub(r'\s+(was\s+)?stolen$', '', clean)
        
        return clean
    
    def _extract_category(self, description: str) -> Optional[str]:
        """Extract item category from description."""
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in description:
                    logger.debug(f"Found category '{category}' via keyword '{keyword}'")
                    return category
        return None
    
    def _extract_brand(self, description: str, category: Optional[str] = None) -> Optional[str]:
        """Extract brand from description."""
        # Check category-specific brands first
        if category and category in self.BRAND_PATTERNS:
            for brand in self.BRAND_PATTERNS[category]:
                if brand in description:
                    logger.debug(f"Found brand '{brand}' in category '{category}'")
                    return brand.title()
        
        # Check all brands
        for brand_list in self.BRAND_PATTERNS.values():
            for brand in brand_list:
                if brand in description:
                    logger.debug(f"Found brand '{brand}'")
                    return brand.title()
        
        return None
    
    def _extract_model(self, description: str) -> Optional[str]:
        """Extract model from description."""
        for pattern in self.MODEL_PATTERNS:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                model = match.group(1).upper()
                logger.debug(f"Found model '{model}' with pattern '{pattern}'")
                return model
        return None
    
    def _extract_specifications(self, description: str) -> Dict[str, str]:
        """Extract specifications from description."""
        specs = {}
        
        # Size/dimension specifications
        for pattern in self.SIZE_PATTERNS:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 2:  # size + unit
                        specs['size'] = f"{match[0]}{match[1]}"
                    elif len(match) == 2 and 'x' in description:  # dimensions
                        specs['dimensions'] = f"{match[0]}x{match[1]}"
                else:
                    if any(unit in match.lower() for unit in ['gb', 'tb', 'mb']):
                        specs['storage'] = match
                    elif any(unit in match.lower() for unit in ['hz', 'mhz', 'ghz']):
                        specs['frequency'] = match
        
        # Color extraction
        colors = ['black', 'white', 'red', 'blue', 'green', 'yellow', 'orange', 'purple',
                 'pink', 'brown', 'gray', 'grey', 'silver', 'gold', 'rose gold']
        for color in colors:
            if color in description:
                specs['color'] = color
                break
        
        return specs
    
    def _extract_keywords(self, description: str) -> List[str]:
        """Extract relevant keywords from description."""
        # Remove common stop words
        stop_words = {'a', 'an', 'the', 'is', 'was', 'were', 'been', 'have', 'has', 'had',
                     'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
                     'must', 'can', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
                     'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
                     'after', 'above', 'below', 'between', 'among', 'this', 'that', 'these',
                     'those', 'my', 'your', 'his', 'her', 'its', 'our', 'their'}
        
        # Extract words (alphanumeric sequences)
        words = re.findall(r'\b\w+\b', description.lower())
        
        # Filter out stop words and very short words
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        # Remove duplicates while preserving order
        unique_keywords = []
        for keyword in keywords:
            if keyword not in unique_keywords:
                unique_keywords.append(keyword)
        
        return unique_keywords[:10]  # Return top 10 keywords