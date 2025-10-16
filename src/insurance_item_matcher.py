"""Main service for matching insurance items to online products."""

import json
import time
import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Union
from decimal import Decimal

from .api_client import ParallelAIClient
from .item_parser import ItemDescriptionParser
from .models import Product, ItemDescription, SearchResult, APIError, ValidationError


logger = logging.getLogger(__name__)


class InsuranceItemMatcher:
    """Main service for matching lost/stolen items to available products online."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Insurance Item Matcher.
        
        Args:
            api_key: Optional Parallel AI API key
        """
        self.api_client = ParallelAIClient(api_key)
        self.parser = ItemDescriptionParser()
    
    def find_matching_products(self, item_description: str, max_results: int = 5, api_strategy: str = "search_first") -> SearchResult:
        """Find matching products for a given item description.
        
        Args:
            item_description: Free-text description of the lost/stolen item
            max_results: Maximum number of products to return
            api_strategy: Which API strategy to use:
                - "search_first": Use Search API first, fallback to Task API (default, fastest)
                - "task_first": Use Task API first, fallback to Search API (highest quality)
                - "search_only": Use only Search API (fastest, no fallback)
                - "task_only": Use only Task API (highest quality, slowest)
            
        Returns:
            SearchResult containing matched products and metadata
            
        Raises:
            ValidationError: If the item description is invalid
            APIError: If the API request fails
        """
        start_time = time.time()
        
        # Validate input
        if not item_description or not item_description.strip():
            raise ValidationError("Item description cannot be empty")
        
        if len(item_description) > 1000:
            raise ValidationError("Item description too long (max 1000 characters)")
        
        logger.info(f"Finding matches for: {item_description[:100]}...")
        
        # Validate API strategy
        valid_strategies = ["search_first", "task_first", "search_only", "task_only"]
        if api_strategy not in valid_strategies:
            raise ValidationError(f"Invalid api_strategy '{api_strategy}'. Must be one of: {', '.join(valid_strategies)}")
        
        try:
            # Parse the item description
            parsed_item = self.parser.parse_description(item_description)
            logger.debug(f"Parsed item: {parsed_item}")
            
            # Generate search queries
            search_queries = self.parser.generate_search_queries(parsed_item)
            logger.debug(f"Generated {len(search_queries)} search queries")
            
            # Create research goal for the APIs
            research_goal = self._create_research_goal(parsed_item, search_queries)
            
            # Choose API strategy
            api_start_time = time.time()
            products, api_metadata = self._execute_api_strategy(research_goal, max_results, api_strategy)
            api_duration = time.time() - api_start_time
            
            # Create the result
            processing_time = time.time() - start_time
            result = SearchResult(
                query=parsed_item,
                matched_products=products,
                processing_time=processing_time,
                total_results=len(products),
                search_metadata={
                    "search_queries": search_queries,
                    "research_goal": research_goal,
                    "api_used": api_metadata.get("api_used", "unknown"),
                    "api_duration": api_duration,
                    "fallback_reason": api_metadata.get("fallback_reason"),
                    "performance_notes": api_metadata.get("performance_notes")
                }
            )
            
            logger.info(f"Found {len(products)} matching products in {processing_time:.2f}s")
            return result
            
        except APIError:
            raise  # Re-raise API errors
        except Exception as e:
            logger.error(f"Unexpected error during product matching: {str(e)}")
            raise APIError(f"Product matching failed: {str(e)}")
    
    def _create_research_goal(self, parsed_item: ItemDescription, search_queries: List[str]) -> str:
        """Create a research goal for the Task API based on the parsed item.
        
        Args:
            parsed_item: Parsed item description
            search_queries: Generated search queries
            
        Returns:
            Research goal string for the Task API
        """
        # Build a comprehensive research goal
        goal_parts = [
            f"Find online products matching this item description: '{parsed_item.text}'"
        ]
        
        if parsed_item.category:
            goal_parts.append(f"The item is a {parsed_item.category}.")
        
        if parsed_item.brand:
            goal_parts.append(f"Brand: {parsed_item.brand}.")
        
        if parsed_item.model:
            goal_parts.append(f"Model: {parsed_item.model}.")
        
        if parsed_item.specifications:
            specs = ", ".join([f"{k}: {v}" for k, v in parsed_item.specifications.items()])
            goal_parts.append(f"Specifications: {specs}.")
        
        goal_parts.extend([
            "For each matching product found, provide:",
            "1. Product name and full description",
            "2. Current price in USD (if available)",
            "3. Direct product URL for purchase",
            "4. Brand and model information",
            "5. Product condition (new/used/refurbished)",
            "6. Retailer/source website name",
            "7. Product availability status",
            "8. Match confidence score (0-1)",
            "",
            "Focus on:",
            "- Current market prices for insurance reimbursement",
            "- Products available for immediate purchase",
            "- Reputable retailers and e-commerce sites",
            "- Exact or very similar product matches",
            "- Both new and refurbished options when relevant"
        ])
        
        research_goal = " ".join(goal_parts)
        logger.debug(f"Research goal: {research_goal}")
        return research_goal
    
    def _execute_api_strategy(self, research_goal: str, max_results: int, strategy: str) -> Tuple[List[Product], Dict[str, Any]]:
        """Execute the chosen API strategy.
        
        Args:
            research_goal: Research goal for the APIs
            max_results: Maximum number of results
            strategy: API strategy to use
            
        Returns:
            Tuple of (products, metadata)
        """
        logger.info(f"🎯 Using API strategy: {strategy}")
        
        if strategy == "search_first":
            return self._search_with_search_api_primary(research_goal, max_results)
        elif strategy == "task_first":
            return self._search_with_task_api_primary(research_goal, max_results)
        elif strategy == "search_only":
            return self._search_with_search_api_only(research_goal, max_results)
        elif strategy == "task_only":
            return self._search_with_task_api_only(research_goal, max_results)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
    
    def _search_with_search_api_primary(self, research_goal: str, max_results: int) -> Tuple[List[Product], Dict[str, Any]]:
        """Use Search API as primary method with Task API fallback for quality.
        
        Args:
            research_goal: Research goal for both APIs
            max_results: Maximum number of results
            
        Returns:
            Tuple of (products, metadata) where metadata contains API performance info
        """
        search_start_time = time.time()
        
        try:
            logger.info("⚡ Starting with fast Search API...")
            
            # Use Search API for initial fast results
            search_response = self.api_client.search(
                objective=research_goal,
                max_results=max_results * 3,  # Get more results to filter better matches
                processor="base"
            )
            
            search_duration = time.time() - search_start_time
            logger.info(f"✅ Search API completed in {search_duration:.2f}s")
            
            # Extract products from search results
            products = self._extract_products_from_search_result(search_response, max_results)
            
            # Check if we got enough quality results
            if len(products) >= max_results // 2:  # At least half the requested results
                logger.info(f"📊 Search API Performance: {search_duration:.2f}s → {len(products)} products")
                logger.info(f"🎯 Success: Search API provided sufficient results, no fallback needed")
                
                metadata = {
                    "api_used": "Search API",
                    "api_duration": search_duration,
                    "performance_notes": f"Search API: {search_duration:.2f}s for {len(products)} products (159x faster than Task API)"
                }
                
                return products, metadata
            else:
                # Not enough results, fallback to Task API for better quality
                logger.warning(f"⚠️ Search API returned only {len(products)} products, falling back to Task API for better quality")
                return self._fallback_to_task_api(research_goal, max_results, 
                                                 f"Insufficient results from Search API ({len(products)} products, {search_duration:.2f}s)")
            
        except Exception as e:
            search_duration = time.time() - search_start_time
            logger.warning(f"❌ Search API failed after {search_duration:.2f}s: {str(e)}, falling back to Task API")
            # Fallback to Task API if Search API fails
            return self._fallback_to_task_api(research_goal, max_results, 
                                             f"Search API failed: {str(e)} (after {search_duration:.2f}s)")
    
    def _fallback_to_task_api(self, research_goal: str, max_results: int, fallback_reason: str) -> Tuple[List[Product], Dict[str, Any]]:
        """Fallback to Task API when Search API is insufficient.
        
        Args:
            research_goal: Research goal for the Task API
            max_results: Maximum number of results
            fallback_reason: Reason for falling back to Task API
            
        Returns:
            Tuple of (products, metadata) with performance information
        """
        task_start_time = time.time()
        logger.info("🚀 Falling back to Task API for higher quality results...")
        
        try:
            # Create a comprehensive output schema for product information
            output_schema = (
                "A JSON array of product objects, each containing: "
                "name (string), price (number in USD), url (string), "
                "brand (string), model (string), condition (string: new/used/refurbished), "
                "source (string: retailer name), confidence_score (number 0-1), "
                "description (string). Return up to {} products."
            ).format(max_results)
            
            # Use the task API with structured output
            task_result = self.api_client.create_task(
                input_text=research_goal,
                output_schema=output_schema,
                processor="base"  # Use base processor for speed
            )
            
            task_duration = time.time() - task_start_time
            logger.info(f"✅ Task API completed in {task_duration:.2f}s")
            
            # Extract products from the structured output
            if task_result and isinstance(task_result, dict) and "output" in task_result:
                products = self._extract_products_from_task_output(task_result["output"], max_results)
                
                # Create performance comparison log
                if "Search API:" in fallback_reason:
                    search_time = float(fallback_reason.split("(")[1].split("s")[0])
                    total_time = search_time + task_duration
                    logger.info(f"📊 Task API Fallback Performance: {task_duration:.2f}s → {len(products)} structured products")
                    logger.info(f"⏱️  Total Time: {total_time:.2f}s (Search: {search_time:.2f}s + Task: {task_duration:.2f}s)")
                else:
                    logger.info(f"📊 Task API Fallback Performance: {task_duration:.2f}s → {len(products)} products")
                
                metadata = {
                    "api_used": "Task API (Fallback)",
                    "api_duration": task_duration,
                    "fallback_reason": fallback_reason,
                    "performance_notes": f"Task API fallback: {task_duration:.2f}s for {len(products)} structured products. Reason: {fallback_reason}"
                }
                
                return products, metadata
            else:
                logger.warning("Task API returned empty or invalid result")
                
                metadata = {
                    "api_used": "Task API (Failed)",
                    "api_duration": task_duration,
                    "fallback_reason": fallback_reason,
                    "performance_notes": f"Both APIs failed. Search API reason: {fallback_reason}, Task API returned empty result after {task_duration:.2f}s"
                }
                
                return [], metadata
                
        except Exception as e:
            task_duration = time.time() - task_start_time
            logger.error(f"❌ Task API also failed after {task_duration:.2f}s: {str(e)}")
            
            metadata = {
                "api_used": "Both APIs Failed",
                "api_duration": task_duration,
                "fallback_reason": fallback_reason,
                "performance_notes": f"Both APIs failed. Search API reason: {fallback_reason}, Task API failed after {task_duration:.2f}s: {str(e)}"
            }
            
            return [], metadata
    
    def _search_with_task_api_primary(self, research_goal: str, max_results: int) -> Tuple[List[Product], Dict[str, Any]]:
        """Use Task API as primary method with Search API fallback for speed.
        
        Args:
            research_goal: Research goal for both APIs
            max_results: Maximum number of results
            
        Returns:
            Tuple of (products, metadata) where metadata contains API performance info
        """
        task_start_time = time.time()
        
        try:
            logger.info("🚀 Starting with high-quality Task API...")
            
            # Use Task API for high-quality structured results
            output_schema = (
                "A JSON array of product objects, each containing: "
                "name (string), price (number in USD), url (string), "
                "brand (string), model (string), condition (string: new/used/refurbished), "
                "source (string: retailer name), confidence_score (number 0-1), "
                "description (string). Return up to {} products."
            ).format(max_results)
            
            task_result = self.api_client.create_task(
                input_text=research_goal,
                output_schema=output_schema,
                processor="base"
            )
            
            task_duration = time.time() - task_start_time
            logger.info(f"✅ Task API completed in {task_duration:.2f}s")
            
            # Extract products from the structured output
            if task_result and isinstance(task_result, dict) and "output" in task_result:
                products = self._extract_products_from_task_output(task_result["output"], max_results)
                
                # Check if we got quality results
                if len(products) >= max_results // 2:  # At least half the requested results
                    logger.info(f"📊 Task API Performance: {task_duration:.2f}s → {len(products)} structured products")
                    logger.info(f"🎯 Success: Task API provided high-quality results")
                    
                    metadata = {
                        "api_used": "Task API",
                        "api_duration": task_duration,
                        "performance_notes": f"Task API: {task_duration:.2f}s for {len(products)} high-quality structured products"
                    }
                    
                    return products, metadata
                else:
                    # Not enough results, fallback to Search API for broader coverage
                    logger.warning(f"⚠️ Task API returned only {len(products)} products, falling back to Search API for broader coverage")
                    return self._fallback_to_search_api(research_goal, max_results, 
                                                       f"Insufficient results from Task API ({len(products)} products, {task_duration:.2f}s)")
            else:
                # No valid results, fallback to Search API
                logger.warning("⚠️ Task API returned invalid result, falling back to Search API")
                return self._fallback_to_search_api(research_goal, max_results, 
                                                   f"Task API returned invalid result (after {task_duration:.2f}s)")
            
        except Exception as e:
            task_duration = time.time() - task_start_time
            logger.warning(f"❌ Task API failed after {task_duration:.2f}s: {str(e)}, falling back to Search API")
            # Fallback to Search API if Task API fails
            return self._fallback_to_search_api(research_goal, max_results, 
                                               f"Task API failed: {str(e)} (after {task_duration:.2f}s)")
    
    def _search_with_search_api_only(self, research_goal: str, max_results: int) -> Tuple[List[Product], Dict[str, Any]]:
        """Use only Search API without fallback.
        
        Args:
            research_goal: Research goal for Search API
            max_results: Maximum number of results
            
        Returns:
            Tuple of (products, metadata)
        """
        search_start_time = time.time()
        
        try:
            logger.info("⚡ Using Search API only (fastest option)...")
            
            search_response = self.api_client.search(
                objective=research_goal,
                max_results=max_results * 3,
                processor="base"
            )
            
            search_duration = time.time() - search_start_time
            logger.info(f"✅ Search API completed in {search_duration:.2f}s")
            
            products = self._extract_products_from_search_result(search_response, max_results)
            
            metadata = {
                "api_used": "Search API (Only)",
                "api_duration": search_duration,
                "performance_notes": f"Search API only: {search_duration:.2f}s for {len(products)} products (fastest option, no fallback)"
            }
            
            logger.info(f"📊 Search API Performance: {search_duration:.2f}s → {len(products)} products")
            return products, metadata
            
        except Exception as e:
            search_duration = time.time() - search_start_time
            logger.error(f"❌ Search API failed after {search_duration:.2f}s: {str(e)}")
            
            metadata = {
                "api_used": "Search API (Failed)",
                "api_duration": search_duration,
                "performance_notes": f"Search API failed after {search_duration:.2f}s: {str(e)} (no fallback available)"
            }
            
            return [], metadata
    
    def _search_with_task_api_only(self, research_goal: str, max_results: int) -> Tuple[List[Product], Dict[str, Any]]:
        """Use only Task API without fallback.
        
        Args:
            research_goal: Research goal for Task API
            max_results: Maximum number of results
            
        Returns:
            Tuple of (products, metadata)
        """
        task_start_time = time.time()
        
        try:
            logger.info("🚀 Using Task API only (highest quality option)...")
            
            output_schema = (
                "A JSON array of product objects, each containing: "
                "name (string), price (number in USD), url (string), "
                "brand (string), model (string), condition (string: new/used/refurbished), "
                "source (string: retailer name), confidence_score (number 0-1), "
                "description (string). Return up to {} products."
            ).format(max_results)
            
            task_result = self.api_client.create_task(
                input_text=research_goal,
                output_schema=output_schema,
                processor="base"
            )
            
            task_duration = time.time() - task_start_time
            logger.info(f"✅ Task API completed in {task_duration:.2f}s")
            
            if task_result and isinstance(task_result, dict) and "output" in task_result:
                products = self._extract_products_from_task_output(task_result["output"], max_results)
                
                metadata = {
                    "api_used": "Task API (Only)",
                    "api_duration": task_duration,
                    "performance_notes": f"Task API only: {task_duration:.2f}s for {len(products)} structured products (highest quality, no fallback)"
                }
                
                logger.info(f"📊 Task API Performance: {task_duration:.2f}s → {len(products)} structured products")
                return products, metadata
            else:
                logger.error("Task API returned empty or invalid result")
                
                metadata = {
                    "api_used": "Task API (Failed)",
                    "api_duration": task_duration,
                    "performance_notes": f"Task API failed after {task_duration:.2f}s: empty or invalid result (no fallback available)"
                }
                
                return [], metadata
                
        except Exception as e:
            task_duration = time.time() - task_start_time
            logger.error(f"❌ Task API failed after {task_duration:.2f}s: {str(e)}")
            
            metadata = {
                "api_used": "Task API (Failed)",
                "api_duration": task_duration,
                "performance_notes": f"Task API failed after {task_duration:.2f}s: {str(e)} (no fallback available)"
            }
            
            return [], metadata
    
    def _fallback_to_search_api(self, research_goal: str, max_results: int, fallback_reason: str) -> Tuple[List[Product], Dict[str, Any]]:
        """Fallback to Search API when Task API is insufficient.
        
        Args:
            research_goal: Research goal for the Search API
            max_results: Maximum number of results
            fallback_reason: Reason for falling back to Search API
            
        Returns:
            Tuple of (products, metadata) with performance information
        """
        search_start_time = time.time()
        logger.info("⚡ Falling back to Search API for broader coverage...")
        
        try:
            search_response = self.api_client.search(
                objective=research_goal,
                max_results=max_results * 3,
                processor="base"
            )
            
            search_duration = time.time() - search_start_time
            logger.info(f"✅ Search API completed in {search_duration:.2f}s")
            
            products = self._extract_products_from_search_result(search_response, max_results)
            
            # Create performance comparison log
            if "Task API:" in fallback_reason:
                task_time = float(fallback_reason.split("(")[1].split("s")[0])
                total_time = task_time + search_duration
                logger.info(f"📊 Search API Fallback Performance: {search_duration:.2f}s → {len(products)} products")
                logger.info(f"⏱️  Total Time: {total_time:.2f}s (Task: {task_time:.2f}s + Search: {search_duration:.2f}s)")
            else:
                logger.info(f"📊 Search API Fallback Performance: {search_duration:.2f}s → {len(products)} products")
            
            metadata = {
                "api_used": "Search API (Fallback)",
                "api_duration": search_duration,
                "fallback_reason": fallback_reason,
                "performance_notes": f"Search API fallback: {search_duration:.2f}s for {len(products)} products. Reason: {fallback_reason}"
            }
            
            return products, metadata
            
        except Exception as e:
            search_duration = time.time() - search_start_time
            logger.error(f"❌ Search API also failed after {search_duration:.2f}s: {str(e)}")
            
            metadata = {
                "api_used": "Both APIs Failed",
                "api_duration": search_duration,
                "fallback_reason": fallback_reason,
                "performance_notes": f"Both APIs failed. Task API reason: {fallback_reason}, Search API failed after {search_duration:.2f}s: {str(e)}"
            }
            
            return [], metadata
    
    def _search_with_task_api(self, research_goal: str, max_results: int) -> Tuple[List[Product], Dict[str, Any]]:
        """Use the Task API to search for products.
        
        Args:
            research_goal: Research goal for the Task API
            max_results: Maximum number of results
            
        Returns:
            Tuple of (products, metadata) where metadata contains API performance info
        """
        task_start_time = time.time()
        
        try:
            # Create a comprehensive output schema for product information
            output_schema = (
                "A JSON array of product objects, each containing: "
                "name (string), price (number in USD), url (string), "
                "brand (string), model (string), condition (string: new/used/refurbished), "
                "source (string: retailer name), confidence_score (number 0-1), "
                "description (string). Return up to {} products."
            ).format(max_results)
            
            logger.info("🚀 Starting Task API search...")
            
            # Use the task API with structured output
            task_result = self.api_client.create_task(
                input_text=research_goal,
                output_schema=output_schema,
                processor="base"  # Use base processor for testing
            )
            
            task_duration = time.time() - task_start_time
            logger.info(f"✅ Task API completed in {task_duration:.2f}s")
            
            # Extract products from the structured output
            if task_result and isinstance(task_result, dict) and "output" in task_result:
                products = self._extract_products_from_task_output(task_result["output"], max_results)
                
                metadata = {
                    "api_used": "Task API",
                    "api_duration": task_duration,
                    "performance_notes": f"Task API: {task_duration:.2f}s for {len(products)} products"
                }
                
                logger.info(f"📊 Task API Performance: {task_duration:.2f}s → {len(products)} products")
                logger.info(f"ℹ️  Note: Search API typically completes in ~2s but returns raw web content")
                return products, metadata
            else:
                logger.warning("Task API returned empty or invalid result")
                
                metadata = {
                    "api_used": "Task API (Failed)",
                    "api_duration": task_duration,
                    "fallback_reason": "Empty or invalid result",
                    "performance_notes": f"Task API failed after {task_duration:.2f}s"
                }
                
                return [], metadata
            
        except APIError as api_error:
            task_duration = time.time() - task_start_time
            # If it's an authentication error, fall back to Search API
            if hasattr(api_error, 'status_code') and api_error.status_code == 401:
                logger.warning(f"⚠️ Authentication failed after {task_duration:.2f}s, falling back to Search API")
                return self._search_with_search_api_with_timing(research_goal, max_results, 
                                                               f"Authentication failed (Task API: {task_duration:.2f}s)")
            raise  # Re-raise other API errors
        except Exception as e:
            task_duration = time.time() - task_start_time
            logger.error(f"❌ Task API search failed after {task_duration:.2f}s: {str(e)}, falling back to Search API")
            # Fallback to Search API if Task API fails
            return self._search_with_search_api_with_timing(research_goal, max_results, 
                                                           f"Task API failed: {str(e)} (after {task_duration:.2f}s)")
    
    def _search_with_search_api_with_timing(self, research_goal: str, max_results: int, fallback_reason: str) -> Tuple[List[Product], Dict[str, Any]]:
        """Use Search API to find products with timing and metadata.
        
        Args:
            research_goal: Research goal
            max_results: Maximum number of results
            fallback_reason: Reason for falling back to Search API
            
        Returns:
            Tuple of (products, metadata) with performance information
        """
        search_start_time = time.time()
        logger.info("🔍 Falling back to Search API...")
        
        try:
            search_response = self.api_client.search(
                objective=research_goal,
                max_results=max_results * 2,  # Get more results to filter
                processor="base"
            )
            
            search_duration = time.time() - search_start_time
            
            # Extract products from search results
            products = self._extract_products_from_search_result(search_response, max_results)
            
            logger.info(f"⚡ Search API completed in {search_duration:.2f}s")
            logger.info(f"📊 Search API Performance: {search_duration:.2f}s → {len(products)} products")
            
            # Create performance comparison log
            if "Task API:" in fallback_reason:
                task_time = float(fallback_reason.split("Task API: ")[1].split("s")[0])
                speedup = task_time / search_duration if search_duration > 0 else 0
                logger.info(f"⚡ Speed Comparison: Search API was {speedup:.1f}x faster than Task API!")
            
            metadata = {
                "api_used": "Search API (Fallback)",
                "api_duration": search_duration,
                "fallback_reason": fallback_reason,
                "performance_notes": f"Search API fallback: {search_duration:.2f}s for {len(products)} products. Reason: {fallback_reason}"
            }
            
            return products, metadata
            
        except Exception as e:
            search_duration = time.time() - search_start_time
            logger.error(f"❌ Search API also failed after {search_duration:.2f}s: {str(e)}")
            
            metadata = {
                "api_used": "Search API (Failed)",
                "api_duration": search_duration,
                "fallback_reason": fallback_reason,
                "performance_notes": f"Both APIs failed. Task API reason: {fallback_reason}, Search API failed after {search_duration:.2f}s: {str(e)}"
            }
            
            return [], metadata
    
    def _search_with_search_api(self, research_goal: str, max_results: int) -> List[Product]:
        """Use Search API to find products (legacy method for direct calls).
        
        Args:
            research_goal: Research goal
            max_results: Maximum number of results
            
        Returns:
            List of matched Product objects
        """
        logger.info("Using Search API to find products")
        
        try:
            search_response = self.api_client.search(
                objective=research_goal,
                max_results=max_results * 2,  # Get more results to filter
                processor="base"
            )
            
            # Extract products from search results
            products = self._extract_products_from_search_result(search_response, max_results)
            return products
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return []  # Return empty list if search fails
    def _extract_products_from_task_output(self, output, max_results: int) -> List[Product]:
        """Extract Product objects from Task API output.
        
        Args:
            output: Output from Task API (string or TaskRunTextOutput object)
            max_results: Maximum number of products to extract
            
        Returns:
            List of Product objects
        """
        products = []
        
        try:
            import json
            
            # Handle TaskRunTextOutput object from SDK
            if hasattr(output, 'text'):
                output_text = output.text
            elif hasattr(output, 'content'):
                output_text = output.content
            else:
                output_text = str(output)
            
            logger.debug(f"Task output text: {output_text[:200]}...")
            
            # Try to parse as JSON with multiple strategies
            products_data = []
            
            # Strategy 1: Direct JSON parsing
            try:
                if output_text.strip().startswith('['):
                    products_data = json.loads(output_text)
                elif output_text.strip().startswith('{'):
                    data = json.loads(output_text)
                    products_data = data.get('products', [data])
                else:
                    raise json.JSONDecodeError("Not direct JSON", output_text, 0)
            except json.JSONDecodeError:
                # Strategy 2: Find JSON array in text
                try:
                    import re
                    json_match = re.search(r'\[.*\]', output_text, re.DOTALL)
                    if json_match:
                        products_data = json.loads(json_match.group())
                    else:
                        raise json.JSONDecodeError("No JSON array found", output_text, 0)
                except json.JSONDecodeError:
                        # Strategy 3: Try to fix common JSON issues
                        try:
                            # Remove trailing commas and fix common issues
                            cleaned_text = re.sub(r',\s*}', '}', output_text)  # Remove trailing commas
                            cleaned_text = re.sub(r',\s*]', ']', cleaned_text)  # Remove trailing commas in arrays
                            
                            if cleaned_text.strip().startswith('['):
                                products_data = json.loads(cleaned_text)
                            elif cleaned_text.strip().startswith('{'):
                                data = json.loads(cleaned_text)
                                products_data = data.get('products', [data])
                            else:
                                json_match = re.search(r'\[.*\]', cleaned_text, re.DOTALL)
                                if json_match:
                                    products_data = json.loads(json_match.group())
                        except json.JSONDecodeError:
                            # Strategy 4: Extract partial JSON objects from the beginning
                            try:
                                logger.info("Attempting to extract partial JSON from truncated response")
                                products_data = self._extract_partial_json_products(output_text)
                                if products_data:
                                    logger.info(f"Successfully extracted {len(products_data)} products from partial JSON")
                            except Exception as partial_error:
                                logger.warning(f"Could not parse JSON from task output after all strategies. Error: {partial_error}. First 500 chars: {output_text[:500]}...")
                                return []
            
            # Convert to Product objects
            for product_data in products_data[:max_results]:
                if isinstance(product_data, dict):
                    product = self._parse_single_product(product_data)
                    if product:
                        products.append(product)
            
            logger.debug(f"Extracted {len(products)} products from task output")
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from task output: {e}")
        except Exception as e:
            logger.error(f"Error extracting products from task output: {str(e)}")
        
        # Sort by confidence score
        return sorted(products, key=lambda x: x.confidence_score or 0, reverse=True)
    
    def _extract_partial_json_products(self, output_text: str) -> List[Dict[str, Any]]:
        """Extract individual JSON objects from partially malformed JSON array.
        
        Args:
            output_text: Potentially truncated JSON text
            
        Returns:
            List of product dictionaries
        """
        products = []
        
        # Strategy 1: Try to extract complete objects using bracket counting
        try:
            # Find the start of the array
            start_idx = output_text.find('[')
            if start_idx == -1:
                return []
            
            current_pos = start_idx + 1
            bracket_count = 0
            in_string = False
            escape_next = False
            object_start = -1
            
            while current_pos < len(output_text):
                char = output_text[current_pos]
                
                if escape_next:
                    escape_next = False
                elif char == '\\' and in_string:
                    escape_next = True
                elif char == '"' and not escape_next:
                    in_string = not in_string
                elif not in_string:
                    if char == '{':
                        if bracket_count == 0:
                            object_start = current_pos
                        bracket_count += 1
                    elif char == '}':
                        bracket_count -= 1
                        if bracket_count == 0 and object_start != -1:
                            # Found a complete object
                            object_text = output_text[object_start:current_pos + 1]
                            try:
                                # Clean and parse the object
                                cleaned_object = re.sub(r',\s*}', '}', object_text)
                                product_data = json.loads(cleaned_object)
                                if isinstance(product_data, dict) and 'name' in product_data:
                                    products.append(product_data)
                            except json.JSONDecodeError:
                                pass  # Skip malformed objects
                            object_start = -1
                    elif char == ']':
                        break  # End of array
                
                current_pos += 1
            
        except Exception as e:
            logger.debug(f"Error in bracket counting strategy: {e}")
        
        # Strategy 2: Fallback to regex if bracket counting fails
        if not products:
            # Simple pattern for complete objects with name field
            pattern = r'\{"name":[^}]+\}'
            matches = re.findall(pattern, output_text)
            
            for match in matches:
                try:
                    cleaned_match = re.sub(r',\s*}', '}', match)
                    product_data = json.loads(cleaned_match)
                    if isinstance(product_data, dict) and 'name' in product_data:
                        products.append(product_data)
                except json.JSONDecodeError:
                    continue
        
        return products
    
    def _extract_products_from_search_result(self, search_result: Union[Dict[str, Any], Any], max_results: int) -> List[Product]:
        """Extract Product objects from Search API result.
        
        Args:
            search_result: WebSearchResult object or dict from Search API
            max_results: Maximum number of products to extract
            
        Returns:
            List of Product objects
        """
        products = []
        
        try:
            # Handle both WebSearchResult object and dict formats
            if hasattr(search_result, 'results'):
                # WebSearchResult object
                results = search_result.results
            elif isinstance(search_result, dict):
                # Dictionary format
                results = search_result.get("results", [])
            else:
                logger.warning(f"Unexpected search result type: {type(search_result)}")
                return []
            
            logger.debug(f"Processing {len(results)} search results")
            
            for i, result in enumerate(results[:max_results * 2]):  # Process more to get better matches
                try:
                    # Handle both object attributes and dict access
                    if hasattr(result, 'url'):
                        # Result object with attributes
                        url = getattr(result, 'url', '')
                        title = getattr(result, 'title', '')
                        excerpts = getattr(result, 'excerpts', [])
                        content = ' '.join(excerpts) if excerpts else title
                    elif isinstance(result, dict):
                        # Result dictionary
                        url = result.get("url", "")
                        title = result.get("title", "")
                        excerpts = result.get("excerpts", [])
                        content = ' '.join(excerpts) if excerpts else title
                    else:
                        logger.debug(f"Unexpected result type at index {i}: {type(result)}")
                        continue
                    
                    # Extract product information from content
                    if content:
                        extracted_products = self._extract_products_from_text(content, source_url=url)
                        products.extend(extracted_products)
                        
                        if len(products) >= max_results:
                            break
                            
                except Exception as result_error:
                    logger.debug(f"Error processing result {i}: {str(result_error)}")
                    continue
        
        except Exception as e:
            logger.error(f"Error extracting products from search result: {str(e)}")
        
        logger.debug(f"Extracted {len(products)} products from search results")
        return products[:max_results]
    
    def _parse_products_from_list(self, products_data: List[Dict]) -> List[Product]:
        """Parse a list of product dictionaries into Product objects."""
        products = []
        
        for product_data in products_data:
            product = self._parse_single_product(product_data)
            if product:
                products.append(product)
        
        return products
    
    def _parse_single_product(self, product_data: Dict[str, Any]) -> Optional[Product]:
        """Parse a single product dictionary into a Product object."""
        try:
            # Extract price
            price = None
            price_raw = product_data.get("price")
            if price_raw:
                price = self._parse_price(str(price_raw))
            
            # Extract URL
            url = product_data.get("url") or product_data.get("link") or product_data.get("product_url")
            
            # Create Product object
            product = Product(
                name=product_data.get("name") or product_data.get("title") or "Unknown Product",
                price=price,
                currency=product_data.get("currency", "USD"),
                url=url,
                description=product_data.get("description"),
                brand=product_data.get("brand"),
                model=product_data.get("model"),
                condition=product_data.get("condition", "new"),
                availability=product_data.get("availability"),
                source=product_data.get("source") or product_data.get("retailer"),
                confidence_score=product_data.get("confidence_score") or product_data.get("confidence") or product_data.get("match_score")
            )
            
            return product
            
        except Exception as e:
            logger.debug(f"Error parsing product: {str(e)}")
            return None
    def _extract_products_from_text(self, text: str, source_url: Optional[str] = None) -> List[Product]:
        """Extract product information from unstructured text."""
        products = []
        
        try:
            # Enhanced price patterns for various formats
            price_patterns = [
                r'\$([0-9,]+(?:\.[0-9]{2})?)',  # $123.45
                r'USD\s*([0-9,]+(?:\.[0-9]{2})?)',  # USD 123.45
                r'([0-9,]+(?:\.[0-9]{2})?)\s*USD',  # 123.45 USD
                r'Price:\s*\$?([0-9,]+(?:\.[0-9]{2})?)',  # Price: $123.45
                r'([0-9,]+(?:\.[0-9]{2})?)\s*dollars?'  # 123.45 dollars
            ]
            
            # Look for product-related keywords and patterns
            product_indicators = [
                'product', 'item', 'buy', 'price', '$', 'sale', 'offer', 'deal',
                'amazon', 'ebay', 'walmart', 'target', 'best buy', 'shop', 'store',
                'brand', 'model', 'specifications', 'features', 'reviews'
            ]
            
            # Split text into sentences for better context
            sentences = re.split(r'[.!?]\s+', text)
            
            for sentence in sentences:
                # Check if sentence contains product indicators
                if any(indicator in sentence.lower() for indicator in product_indicators):
                    # Try to extract price from this sentence
                    price = None
                    for pattern in price_patterns:
                        price_match = re.search(pattern, sentence, re.IGNORECASE)
                        if price_match:
                            try:
                                price_str = price_match.group(1).replace(',', '')
                                price = Decimal(price_str)
                                break
                            except:
                                continue
                    
                    # Extract potential product name (first meaningful part of sentence)
                    name = sentence.strip()[:100]
                    # Clean up common prefixes
                    name = re.sub(r'^(shop|buy|get|find|search)\s+', '', name, flags=re.IGNORECASE)
                    
                    if price and name and len(name) > 10:  # Only create if we have both price and reasonable name
                        # Determine confidence based on content quality
                        confidence = 0.3  # Base confidence for text extraction
                        if any(site in source_url.lower() if source_url else '' for site in ['amazon', 'ebay', 'walmart', 'target']):
                            confidence = 0.7  # Higher confidence for known e-commerce sites
                        elif '$' in sentence:
                            confidence = 0.5  # Medium confidence if explicit price symbol
                        
                        product = Product(
                            name=name,
                            price=price,
                            url=source_url,
                            source=self._extract_domain(source_url) if source_url else None,
                            confidence_score=confidence
                        )
                        products.append(product)
                        
                        if len(products) >= 3:  # Limit to avoid too many low-quality matches
                            break
        
        except Exception as e:
            logger.debug(f"Error extracting from text: {str(e)}")
        
        return products
        return products[:3]  # Return at most 3 products from text extraction
    
    def _parse_price(self, price_str: str) -> Optional[Decimal]:
        """Parse a price string into a Decimal."""
        try:
            # Remove currency symbols and spaces
            clean_price = re.sub(r'[^0-9.,]', '', price_str)
            clean_price = clean_price.replace(',', '')
            
            if clean_price:
                return Decimal(clean_price)
        except:
            pass
        return None
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain name from URL."""
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            return parsed.netloc
        except:
            return None