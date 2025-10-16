#!/usr/bin/env python3
"""
Main entry point for the Insurance Item Matcher service.

This script provides both Streamlit UI and programmatic access to the service.
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src import InsuranceItemMatcher


def example_usage():
    """Example of how to use the service programmatically."""
    
    # Initialize the matcher
    matcher = InsuranceItemMatcher()
    
    # Example searches
    test_items = [
        "iPhone 16 Pro Max model XYZ123",
        "black couch",
        "Samsung 55 inch TV",
        "MacBook Pro 14-inch 2024"
    ]
    
    print("🔍 Insurance Item Matcher - Programmatic Example\n")
    
    for item in test_items:
        print(f"Searching for: {item}")
        try:
            result = matcher.find_matching_products(item, max_results=3)
            
            if result.matched_products:
                print(f"✅ Found {len(result.matched_products)} products:")
                for i, product in enumerate(result.matched_products, 1):
                    price_str = f"${product.price}" if product.price else "N/A"
                    print(f"  {i}. {product.name} - {price_str}")
                    if product.url:
                        print(f"     URL: {product.url}")
            else:
                print("❌ No products found")
            
            print(f"   Processing time: {result.processing_time:.2f}s\n")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "example":
        # Run programmatic example
        example_usage()
    else:
        # Show instructions for running Streamlit app
        print("🔍 Insurance Item Matcher")
        print("")
        print("To run the web interface:")
        print("  streamlit run streamlit_app.py")
        print("")
        print("To run programmatic examples:")
        print("  python main.py example")
        print("")
        print("To install dependencies:")
        print("  pip install -r requirements.txt")
