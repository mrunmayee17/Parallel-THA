#!/usr/bin/env python3
"""
Demo script showing how to use different API strategies with the Insurance Item Matcher.

This script demonstrates all four API strategies:
1. search_first: Search API → Task API fallback (fastest, default)
2. task_first: Task API → Search API fallback (highest quality)  
3. search_only: Only Search API (fastest, no fallback)
4. task_only: Only Task API (highest quality, no fallback)
"""

import sys
import os
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from insurance_item_matcher import InsuranceItemMatcher

def demonstrate_api_strategies():
    """Demonstrate different API strategies."""
    
    # Initialize the matcher
    matcher = InsuranceItemMatcher()
    
    # Example item description
    item_description = "Apple iPhone 14 Pro 128GB Space Black"
    
    strategies = [
        ("search_first", "🔄 Search API first with Task API fallback (Default - Fastest with quality backup)"),
        ("task_first", "🎯 Task API first with Search API fallback (Quality first with speed backup)"),
        ("search_only", "⚡ Search API only (Fastest option, ~2 seconds)"),
        ("task_only", "🚀 Task API only (Highest quality, ~120+ seconds)")
    ]
    
    print(f"🔍 Finding matches for: {item_description}")
    print("=" * 80)
    
    for strategy, description in strategies:
        print(f"\n{description}")
        print("-" * 60)
        
        start_time = time.time()
        
        try:
            result = matcher.find_matching_products(
                item_description=item_description,
                max_results=3,
                api_strategy=strategy
            )
            
            total_time = time.time() - start_time
            
            print(f"✅ Strategy '{strategy}' completed in {total_time:.2f}s")
            print(f"📊 API Used: {result.search_metadata.get('api_used', 'Unknown')}")
            print(f"⏱️  API Duration: {result.search_metadata.get('api_duration', 0):.2f}s")
            print(f"🔢 Found {len(result.matched_products)} products")
            
            if result.search_metadata.get('fallback_reason'):
                print(f"📝 Fallback Reason: {result.search_metadata['fallback_reason']}")
            
            # Show first product as example
            if result.matched_products:
                product = result.matched_products[0]
                print(f"🎯 Top Result: {product.name}")
                if product.price:
                    print(f"💰 Price: ${product.price}")
                if product.confidence_score:
                    print(f"📈 Confidence: {product.confidence_score:.2f}")
            
        except Exception as e:
            total_time = time.time() - start_time
            print(f"❌ Strategy '{strategy}' failed after {total_time:.2f}s: {str(e)}")

def quick_comparison():
    """Quick comparison of search_first vs task_first strategies."""
    
    matcher = InsuranceItemMatcher()
    item = "Samsung Galaxy S23 Ultra 256GB"
    
    print(f"\n🚀 QUICK COMPARISON")
    print("=" * 50)
    print(f"Item: {item}")
    
    for strategy in ["search_first", "task_first"]:
        start_time = time.time()
        
        try:
            result = matcher.find_matching_products(
                item_description=item,
                max_results=5,
                api_strategy=strategy
            )
            
            duration = time.time() - start_time
            api_used = result.search_metadata.get('api_used', 'Unknown')
            
            print(f"\n{strategy.upper():<12}: {duration:.2f}s | {api_used} | {len(result.matched_products)} products")
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"\n{strategy.upper():<12}: {duration:.2f}s | FAILED: {str(e)}")

if __name__ == "__main__":
    print("🔧 Insurance Item Matcher - API Strategy Demonstration")
    print("This demo shows how to choose different API strategies for different use cases.\n")
    
    try:
        # Full demonstration
        demonstrate_api_strategies()
        
        # Quick comparison
        quick_comparison()
        
        print(f"\n" + "=" * 80)
        print("💡 STRATEGY RECOMMENDATIONS:")
        print("• search_first: Best for most use cases (fast + quality fallback)")
        print("• task_first: When you need highest quality and time is less critical")  
        print("• search_only: When you need maximum speed and basic results are OK")
        print("• task_only: When you need only the highest quality structured results")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {str(e)}")
        sys.exit(1)