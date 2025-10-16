"""
Streamlit UI for the Insurance Item Matcher service.

This module provides a user-friendly web interface for finding online product matches
for lost or stolen items to determine insurance reimbursement values.

The interface includes:
- Product search functionality
- Configuration management
- Results display and export
- Search history tracking
"""

import streamlit as st
import pandas as pd
import json
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import time

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.insurance_item_matcher import InsuranceItemMatcher
from src.models import APIError, ValidationError, SearchResult, Product
from src.config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
MAX_SEARCH_HISTORY_SIZE = 5
DEFAULT_MAX_RESULTS = 5
MIN_RESULTS = 1
MAX_RESULTS = 20


class SessionStateManager:
    """Manages Streamlit session state initialization and access."""
    
    @staticmethod
    def initialize_session_state() -> None:
        """Initialize all session state variables with default values."""
        if 'search_history' not in st.session_state:
            st.session_state.search_history = []
        if 'api_key' not in st.session_state:
            st.session_state.api_key = Config.PARALLEL_AI_API_KEY
    
    @staticmethod
    def add_search_to_history(query: str, results_count: int, processing_time: float) -> None:
        """Add a search entry to the history.
        
        Args:
            query: The search query string
            results_count: Number of results found
            processing_time: Time taken for the search in seconds
        """
        search_entry = {
            'query': query,
            'results_count': results_count,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'processing_time': processing_time
        }
        
        # Keep only the most recent searches
        if len(st.session_state.search_history) >= MAX_SEARCH_HISTORY_SIZE:
            st.session_state.search_history.pop(0)
        
        st.session_state.search_history.append(search_entry)


class ConfigurationManager:
    """Handles configuration UI components and validation."""
    
    @staticmethod
    def create_sidebar_configuration() -> Tuple[int, str, str]:
        """Create sidebar with configuration options.
        
        Returns:
            Tuple of (max_results, processor_type, api_strategy)
        """
        st.sidebar.header("Configuration")
        
        # API Key configuration
        ConfigurationManager._render_api_key_section()
        
        # Search settings
        st.sidebar.subheader("Search Settings")
        max_results = ConfigurationManager._get_max_results_setting()
        processor = ConfigurationManager._get_processor_setting()
        api_strategy = ConfigurationManager._get_api_strategy_setting()
        
        # Display current configuration
        ConfigurationManager._display_current_configuration(processor, api_strategy)
        
        # Add strategy recommendations
        ConfigurationManager._display_strategy_recommendations()
        
        return max_results, processor, api_strategy
    
    @staticmethod
    def _render_api_key_section() -> None:
        """Render the API key input section."""
        api_key = st.sidebar.text_input(
            "Parallel AI API Key",
            value=st.session_state.api_key,
            type="password",
            help="Your Parallel AI API key. Leave empty to use environment variable."
        )
        st.session_state.api_key = api_key
    
    @staticmethod
    def _get_max_results_setting() -> int:
        """Get the maximum results setting from user input.
        
        Returns:
            Maximum number of results to return
        """
        return st.sidebar.slider(
            "Max Results",
            min_value=MIN_RESULTS,
            max_value=MAX_RESULTS,
            value=DEFAULT_MAX_RESULTS,
            help="Maximum number of products to return"
        )
    
    @staticmethod
    def _get_processor_setting() -> str:
        """Get the processor type setting from user input.
        
        Returns:
            Selected processor type
        """
        return st.sidebar.selectbox(
            "Processor Type",
            options=["base", "pro", "ultra"],
            index=0,
            help="API processor to use (base is fast and cost-effective)"
        )
    
    @staticmethod
    def _get_api_strategy_setting() -> str:
        """Get the API strategy setting from user input.
        
        Returns:
            Selected API strategy
        """
        return st.sidebar.selectbox(
            "API Strategy",
            options=["search_first", "task_first", "search_only", "task_only"],
            index=0,
            format_func=ConfigurationManager._format_api_strategy,
            help=ConfigurationManager._get_api_strategy_help()
        )
    
    @staticmethod
    def _format_api_strategy(strategy: str) -> str:
        """Format API strategy for display.
        
        Args:
            strategy: The API strategy string
            
        Returns:
            Formatted strategy string
        """
        strategy_labels = {
            "search_first": "🔄 Search First (Recommended)",
            "task_first": "🎯 Task First (High Quality)",
            "search_only": "⚡ Search Only (Fastest)",
            "task_only": "🚀 Task Only (Best Quality)"
        }
        return strategy_labels.get(strategy, strategy)
    
    @staticmethod
    def _get_api_strategy_help() -> str:
        """Get help text for API strategy selection.
        
        Returns:
            Help text string
        """
        return (
            "Choose API strategy:\n"
            "• Search First: Fast results (~2s) with quality fallback\n"
            "• Task First: Quality first (~120s) with speed backup\n"
            "• Search Only: Maximum speed (~2s), no fallback\n"
            "• Task Only: Maximum quality (~120s), no fallback"
        )
    
    @staticmethod
    def _display_current_configuration(processor: str, api_strategy: str) -> None:
        """Display current configuration summary.
        
        Args:
            processor: Selected processor type
            api_strategy: Selected API strategy
        """
        st.sidebar.subheader("Current Configuration")
        
        api_key = st.session_state.api_key
        masked_key = ConfigurationManager._mask_api_key(api_key)
        
        st.sidebar.text(f"API Key: {masked_key}")
        st.sidebar.text(f"Base URL: {Config.PARALLEL_AI_BASE_URL}")
        st.sidebar.text(f"Processor: {processor}")
        st.sidebar.text(f"Strategy: {ConfigurationManager._format_api_strategy(api_strategy)}")
    
    @staticmethod
    def _display_strategy_recommendations() -> None:
        """Display API strategy recommendations in sidebar."""
        with st.sidebar.expander("💡 Strategy Guide", expanded=False):
            st.markdown(
                "**When to use each strategy:**\n\n"
                "🔄 **Search First** (Recommended)\n"
                "- Most insurance claims\n"
                "- Balanced speed and quality\n"
                "- General product searches\n\n"
                "🎯 **Task First** (High Quality)\n"
                "- Expensive items ($1000+)\n"
                "- Complex electronics\n"
                "- Disputed claims\n\n"
                "⚡ **Search Only** (Fastest)\n"
                "- Bulk processing\n"
                "- Quick estimates\n"
                "- Simple items\n\n"
                "🚀 **Task Only** (Best Quality)\n"
                "- Critical assessments\n"
                "- Legal cases\n"
                "- Luxury/specialized items"
            )
    
    @staticmethod
    def _mask_api_key(api_key: str) -> str:
        """Mask API key for display purposes.
        
        Args:
            api_key: The API key to mask
            
        Returns:
            Masked API key string
        """
        if api_key and len(api_key) > 8:
            return f"{api_key[:8]}..."
        return "Not set"


class ProductDisplayManager:
    """Handles product display and formatting."""
    
    @staticmethod
    def display_product_card(product: Product, index: int) -> None:
        """Display a product as an information card.
        
        Args:
            product: Product object to display
            index: Product index for identification
        """
        with st.container():
            product_col, price_col = st.columns([3, 1])
            
            with product_col:
                ProductDisplayManager._render_product_header(product)
                ProductDisplayManager._render_product_details(product)
                ProductDisplayManager._render_product_description(product)
            
            with price_col:
                ProductDisplayManager._render_price_section(product)
                ProductDisplayManager._render_action_button(product)
            
            st.divider()
    
    @staticmethod
    def _render_product_header(product: Product) -> None:
        """Render the product header section.
        
        Args:
            product: Product object containing header information
        """
        st.subheader(product.name)
    
    @staticmethod
    def _render_product_details(product: Product) -> None:
        """Render product details in two columns.
        
        Args:
            product: Product object containing detail information
        """
        details_left, details_right = st.columns(2)
        
        with details_left:
            ProductDisplayManager._render_left_details(product)
        
        with details_right:
            ProductDisplayManager._render_right_details(product)
    
    @staticmethod
    def _render_left_details(product: Product) -> None:
        """Render left column product details.
        
        Args:
            product: Product object containing left column information
        """
        if product.brand:
            st.write(f"**Brand:** {product.brand}")
        if product.model:
            st.write(f"**Model:** {product.model}")
        if product.condition:
            st.write(f"**Condition:** {product.condition}")
    
    @staticmethod
    def _render_right_details(product: Product) -> None:
        """Render right column product details.
        
        Args:
            product: Product object containing right column information
        """
        if product.source:
            st.write(f"**Source:** {product.source}")
        if product.availability:
            st.write(f"**Availability:** {product.availability}")
        if product.confidence_score:
            ProductDisplayManager._render_confidence_score(product.confidence_score)
    
    @staticmethod
    def _render_confidence_score(confidence_score: float) -> None:
        """Render confidence score with progress bar.
        
        Args:
            confidence_score: Confidence score as a float between 0 and 1
        """
        confidence_percentage = confidence_score * 100
        st.write(f"**Match Confidence:** {confidence_percentage:.1f}%")
        st.progress(confidence_score)
    
    @staticmethod
    def _render_product_description(product: Product) -> None:
        """Render expandable product description.
        
        Args:
            product: Product object containing description
        """
        if product.description:
            with st.expander("Product Description"):
                st.write(product.description)
    
    @staticmethod
    def _render_price_section(product: Product) -> None:
        """Render price information section.
        
        Args:
            product: Product object containing price information
        """
        if product.price is not None:
            try:
                # Handle Decimal, float, or int
                if hasattr(product.price, '__float__'):  # Decimal or other numeric types
                    price_value = float(product.price)
                else:
                    price_value = product.price
                
                st.write(f"**Price:** ${price_value:,.2f}")
            except (ValueError, TypeError, AttributeError) as e:
                st.write(f"**Price:** ${str(product.price)}")
        else:
            st.write("**Price:** Not Available")
    
    @staticmethod
    def _render_action_button(product: Product) -> None:
        """Render product action button.
        
        Args:
            product: Product object containing URL information
        """
        if product.url:
            st.link_button(
                "View Product",
                product.url,
                use_container_width=True
            )
        else:
            st.button(
                "No URL Available",
                disabled=True,
                use_container_width=True
            )


class SearchResultsManager:
    """Handles search results display and formatting."""
    
    @staticmethod
    def display_search_results(result: SearchResult) -> None:
        """Display search results in a user-friendly format.
        
        Args:
            result: SearchResult object containing matched products and metadata
        """
        if not result.matched_products:
            st.warning("No matching products found. Try a different description or be more specific.")
            return
        
        SearchResultsManager._display_results_summary(result)
        SearchResultsManager._display_product_cards(result.matched_products)
    
    @staticmethod
    def _display_results_summary(result: SearchResult) -> None:
        """Display summary metrics for search results.
        
        Args:
            result: SearchResult object containing metadata
        """
        summary_col1, summary_col2, summary_col3 = st.columns(3)
        
        with summary_col1:
            st.metric("Products Found", len(result.matched_products))
        
        with summary_col2:
            st.metric("Processing Time", f"{result.processing_time:.2f}s")
        
        with summary_col3:
            average_confidence = SearchResultsManager._calculate_average_confidence(result.matched_products)
            confidence_display = f"{average_confidence:.1%}" if average_confidence else "N/A"
            st.metric("Average Confidence", confidence_display)
        
        st.divider()
    
    @staticmethod
    def _calculate_average_confidence(products: List[Product]) -> Optional[float]:
        """Calculate average confidence score from products.
        
        Args:
            products: List of Product objects
            
        Returns:
            Average confidence score or None if no scores available
        """
        products_with_scores = [p for p in products if p.confidence_score]
        
        if not products_with_scores:
            return None
        
        total_confidence = sum(p.confidence_score for p in products_with_scores)
        return total_confidence / len(products_with_scores)
    
    @staticmethod
    def _display_product_cards(products: List[Product]) -> None:
        """Display product cards for search results.
        
        Args:
            products: List of Product objects to display
        """
        st.subheader("Matching Products")
        
        for index, product in enumerate(products, 1):
            st.markdown(f"### Result {index}")
            ProductDisplayManager.display_product_card(product, index)


class SearchHistoryManager:
    """Handles search history display and interaction."""
    
    @staticmethod
    def display_search_history() -> None:
        """Display search history in sidebar with repeat functionality."""
        if not st.session_state.search_history:
            return
        
        st.sidebar.subheader("Recent Searches")
        
        recent_searches = list(reversed(st.session_state.search_history[-MAX_SEARCH_HISTORY_SIZE:]))
        
        for index, search_entry in enumerate(recent_searches):
            SearchHistoryManager._display_search_entry(search_entry, index)
    
    @staticmethod
    def _display_search_entry(search_entry: Dict[str, Any], index: int) -> None:
        """Display individual search entry with repeat option.
        
        Args:
            search_entry: Dictionary containing search information
            index: Index for unique component keys
        """
        query_preview = SearchHistoryManager._truncate_query(search_entry['query'])
        
        with st.sidebar.expander(f"Search: {query_preview}"):
            st.write(f"**Query:** {search_entry['query']}")
            st.write(f"**Results:** {search_entry['results_count']}")
            st.write(f"**Time:** {search_entry['timestamp']}")
            
            if st.button("Repeat Search", key=f"repeat_search_{index}"):
                st.session_state.repeat_search = search_entry['query']
                st.rerun()
    
    @staticmethod
    def _truncate_query(query: str, max_length: int = 30) -> str:
        """Truncate query for display purposes.
        
        Args:
            query: Original query string
            max_length: Maximum length before truncation
            
        Returns:
            Truncated query string with ellipsis if needed
        """
        return f"{query[:max_length]}..." if len(query) > max_length else query


class ExportManager:
    """Handles data export functionality."""
    
    @staticmethod
    def export_results_to_json(result: SearchResult) -> str:
        """Export search results to JSON format.
        
        Args:
            result: SearchResult object to export
            
        Returns:
            JSON string representation of the results
        """
        try:
            result_dict = {
                "query": result.query.model_dump() if hasattr(result.query, 'model_dump') else result.query.dict(),
                "matched_products": [product.model_dump() if hasattr(product, 'model_dump') else product.dict() for product in result.matched_products],
                "processing_time": result.processing_time,
                "total_results": result.total_results,
                "search_metadata": result.search_metadata,
                "export_timestamp": datetime.now().isoformat()
            }
            return json.dumps(result_dict, indent=2, default=str)
        
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}")
            raise
    
    @staticmethod
    def create_csv_dataframe(products: List[Product]) -> pd.DataFrame:
        """Create pandas DataFrame from products for CSV export.
        
        Args:
            products: List of Product objects
            
        Returns:
            pandas DataFrame ready for CSV export
        """
        try:
            data = []
            for product in products:
                # Handle price conversion safely
                price_value = None
                if product.price is not None:
                    try:
                        if hasattr(product.price, '__float__'):
                            price_value = float(product.price)
                        else:
                            price_value = product.price
                    except (ValueError, TypeError, AttributeError):
                        price_value = str(product.price)
                
                data.append({
                    'Product Name': product.name,
                    'Price': price_value,
                    'Brand': product.brand,
                    'Model': product.model,
                    'Condition': product.condition,
                    'Source': product.source,
                    'Confidence': f"{product.confidence_score:.1%}" if product.confidence_score else None,
                    'URL': str(product.url) if product.url else None
                })
            
            return pd.DataFrame(data)
        
        except Exception as e:
            logger.error(f"Error creating CSV DataFrame: {e}")
            raise


class InsuranceItemMatcherApp:
    """Main application class for the Insurance Item Matcher Streamlit interface."""
    
    def __init__(self):
        """Initialize the application."""
        self._configure_page()
        SessionStateManager.initialize_session_state()
    
    def _configure_page(self) -> None:
        """Configure Streamlit page settings."""
        st.set_page_config(
            page_title="Insurance Item Matcher",
            page_icon="🔍",
            layout="wide",
            initial_sidebar_state="expanded"
        )
    
    def run(self) -> None:
        """Run the main application."""
        try:
            self._render_header()
            max_results, processor, api_strategy = self._setup_sidebar()
            search_parameters = self._render_search_interface(max_results)
            
            if search_parameters:
                search_parameters['api_strategy'] = api_strategy
                self._process_search_request(search_parameters)
            
            self._render_footer()
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            st.error("An unexpected error occurred. Please refresh the page.")
    
    def _render_header(self) -> None:
        """Render application header and description."""
        st.title("Insurance Item Matcher")
        st.markdown(
            "Find online product matches for lost or stolen items to determine "
            "insurance reimbursement values. Enter a description of your item below "
            "and we'll find the best matching products with current prices."
        )
    
    def _setup_sidebar(self) -> Tuple[int, str, str]:
        """Setup sidebar configuration and history.
        
        Returns:
            Tuple of (max_results, processor_type, api_strategy)
        """
        max_results, processor, api_strategy = ConfigurationManager.create_sidebar_configuration()
        SearchHistoryManager.display_search_history()
        return max_results, processor, api_strategy
    
    def _render_search_interface(self, default_max_results: int) -> Optional[Dict[str, Any]]:
        """Render the search interface and handle form submission.
        
        Args:
            default_max_results: Default maximum results value
            
        Returns:
            Search parameters if form submitted, None otherwise
        """
        st.header("Search for Products")
        
        with st.form("product_search_form", clear_on_submit=False):
            search_params = self._get_search_form_inputs(default_max_results)
            submitted = st.form_submit_button(
                "Search Products", 
                use_container_width=True, 
                type="primary"
            )
            
            if submitted or self._handle_repeat_search():
                return self._validate_search_inputs(search_params)
        
        return None
    
    def _get_search_form_inputs(self, default_max_results: int) -> Dict[str, Any]:
        """Get inputs from search form.
        
        Args:
            default_max_results: Default maximum results value
            
        Returns:
            Dictionary containing form inputs
        """
        item_description = st.text_area(
            "Item Description",
            placeholder=self._get_placeholder_text(),
            height=100,
            help="Describe your item. Be as specific as possible for better matches."
        )
        
        # Advanced options
        with st.expander("Advanced Options"):
            advanced_col1, advanced_col2 = st.columns(2)
            
            with advanced_col1:
                custom_max_results = st.number_input(
                    "Custom Max Results",
                    min_value=MIN_RESULTS,
                    max_value=MAX_RESULTS,
                    value=default_max_results,
                    help="Override sidebar setting"
                )
            
            with advanced_col2:
                include_refurbished = st.checkbox(
                    "Include Refurbished Items",
                    value=True,
                    help="Include refurbished/used items in search"
                )
        
        return {
            'description': item_description,
            'max_results': custom_max_results,
            'include_refurbished': include_refurbished
        }
    
    def _get_placeholder_text(self) -> str:
        """Get placeholder text for item description input.
        
        Returns:
            Placeholder text string
        """
        return (
            "Enter a description of your lost/stolen item...\n\n"
            "Examples:\n"
            "• iPhone 16 Pro Max 256GB Space Black model XYZ123\n"
            "• black leather couch\n"
            "• Samsung 55 inch TV\n"
            "• MacBook Pro 14-inch 2024"
        )
    
    def _handle_repeat_search(self) -> bool:
        """Handle repeat search from history.
        
        Returns:
            True if repeat search should be processed, False otherwise
        """
        if hasattr(st.session_state, 'repeat_search'):
            # This would need to be handled differently in the actual form
            # For now, we'll return False and handle it in the calling method
            return True
        return False
    
    def _validate_search_inputs(self, search_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate search inputs.
        
        Args:
            search_params: Dictionary containing search parameters
            
        Returns:
            Validated search parameters or None if invalid
        """
        description = search_params.get('description', '').strip()
        
        if not description:
            st.warning("Please enter an item description to search.")
            return None
        
        search_params['description'] = description
        return search_params
    
    def _process_search_request(self, search_params: Dict[str, Any]) -> None:
        """Process the search request and display results.
        
        Args:
            search_params: Dictionary containing validated search parameters
        """
        try:
            # Initialize matcher
            with st.spinner("Initializing search service..."):
                matcher = InsuranceItemMatcher(api_key=st.session_state.api_key)
            
            # Perform search
            api_strategy = search_params.get('api_strategy', 'search_first')
            strategy_description = ConfigurationManager._format_api_strategy(api_strategy)
            
            with st.spinner(f"Searching for matching products using {strategy_description}... This may take a moment."):
                search_start_time = time.time()
                search_result = matcher.find_matching_products(
                    item_description=search_params['description'],
                    max_results=search_params['max_results'],
                    api_strategy=api_strategy
                )
                search_duration = time.time() - search_start_time
            
            # Add to search history
            SessionStateManager.add_search_to_history(
                query=search_params['description'],
                results_count=len(search_result.matched_products),
                processing_time=search_duration
            )
            
            # Display results with performance information
            st.success(f"Search completed in {search_duration:.2f} seconds!")
            
            # Display performance metrics
            self._display_performance_info(search_result)
            
            # Simple, reliable product display
            if search_result.matched_products:
                st.subheader(f"Found {len(search_result.matched_products)} Products:")
                
                for i, product in enumerate(search_result.matched_products, 1):
                    st.markdown(f"### Result {i}")
                    st.subheader(product.name)
                    
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        if product.brand:
                            st.write(f"**Brand:** {product.brand}")
                        if product.condition:
                            st.write(f"**Condition:** {product.condition}")
                        if product.source:
                            st.write(f"**Source:** {product.source}")
                        if product.confidence_score:
                            st.write(f"**Match Confidence:** {product.confidence_score:.1%}")
                        if product.description:
                            with st.expander("Product Description"):
                                st.write(product.description)
                    
                    with col2:
                        if product.price:
                            st.write(f"**Price:** ${float(product.price):,.2f}")
                        else:
                            st.write("**Price:** Not Available")
                        
                        if product.url:
                            st.link_button("View Product", str(product.url), use_container_width=True)
                    
                    st.divider()
            else:
                st.warning("No matching products found. Try a different description or be more specific.")
            
            # Export options
            if search_result.matched_products:
                self._render_export_options(search_result)
                
        except ValidationError as e:
            self._handle_validation_error(e)
        except APIError as e:
            self._handle_api_error(e)
        except Exception as e:
            self._handle_unexpected_error(e)
    
    def _render_export_options(self, search_result: SearchResult) -> None:
        """Render export options for search results.
        
        Args:
            search_result: SearchResult object containing products to export
        """
        st.divider()
        st.subheader("Export Results")
        
        export_col1, export_col2 = st.columns(2)
        
        with export_col1:
            json_data = ExportManager.export_results_to_json(search_result)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            st.download_button(
                label="Download as JSON",
                data=json_data,
                file_name=f"insurance_search_results_{timestamp}.json",
                mime="application/json",
                use_container_width=True
            )
        
        with export_col2:
            csv_dataframe = ExportManager.create_csv_dataframe(search_result.matched_products)
            csv_data = csv_dataframe.to_csv(index=False)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            st.download_button(
                label="Download as CSV",
                data=csv_data,
                file_name=f"insurance_products_{timestamp}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    def _display_performance_info(self, search_result: SearchResult) -> None:
        """Display API performance information in an expandable section.
        
        Args:
            search_result: SearchResult containing performance metadata
        """
        with st.expander("🔧 Performance Information", expanded=False):
            metadata = search_result.search_metadata
            
            # Display strategy information
            st.info(
                f"**Search Strategy Used:** This search used the configured API strategy. "
                f"Different strategies optimize for speed vs quality based on your needs."
            )
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                api_used = metadata.get('api_used', 'Unknown')
                st.metric("API Used", api_used)
                
            with col2:
                api_duration = metadata.get('api_duration', 0)
                st.metric("API Duration", f"{api_duration:.2f}s")
                
            with col3:
                total_time = search_result.processing_time
                st.metric("Total Time", f"{total_time:.2f}s")
            
            # Show fallback information if applicable
            fallback_reason = metadata.get('fallback_reason')
            if fallback_reason:
                st.warning(f"**Fallback Triggered:** {fallback_reason}")
                
                # Show speed comparison if available
                performance_notes = metadata.get('performance_notes', '')
                if "faster than" in performance_notes:
                    st.info(f"⚡ {performance_notes}")
            
            # Performance details
            if metadata.get('performance_notes'):
                st.text_area(
                    "Performance Details", 
                    metadata['performance_notes'], 
                    height=100, 
                    disabled=True
                )
    
    def _handle_validation_error(self, error: ValidationError) -> None:
        """Handle validation errors.
        
        Args:
            error: ValidationError exception
        """
        st.error(f"**Validation Error:** {str(error)}")
        st.info("**Tip:** Make sure your item description is not empty and under 1000 characters.")
    
    def _handle_api_error(self, error: APIError) -> None:
        """Handle API errors.
        
        Args:
            error: APIError exception
        """
        st.error(f"**API Error:** {str(error)}")
        if hasattr(error, 'status_code') and error.status_code:
            st.info(f"Status Code: {error.status_code}")
        st.info("**Tip:** Check your API key and internet connection.")
    
    def _handle_unexpected_error(self, error: Exception) -> None:
        """Handle unexpected errors.
        
        Args:
            error: Exception object
        """
        logger.error(f"Unexpected error: {error}")
        st.error(f"**Unexpected Error:** {str(error)}")
        st.info("**Tip:** Try refreshing the page or contact support if the issue persists.")
    
    def _render_footer(self) -> None:
        """Render application footer with examples and information."""
        st.divider()
        
        # Usage examples
        with st.expander("Usage Examples & Tips"):
            self._render_usage_examples()
        
        # About section
        with st.expander("About Insurance Item Matcher"):
            self._render_about_section()
    
    def _render_usage_examples(self) -> None:
        """Render usage examples and tips."""
        example_col1, example_col2 = st.columns(2)
        
        with example_col1:
            st.markdown(
                "**Detailed Descriptions (Better Results):**\n"
                "- iPhone 16 Pro Max 256GB Space Black model A2894\n"
                "- Samsung Galaxy S24 Ultra 512GB Titanium Gray\n"
                "- MacBook Pro 14-inch M3 2024 Space Gray 1TB\n"
                "- Sony WH-1000XM5 Noise Canceling Headphones Black"
            )
        
        with example_col2:
            st.markdown(
                "**General Descriptions (Good Results):**\n"
                "- black leather couch\n"
                "- Samsung 55 inch TV\n"
                "- Nike Air Jordan shoes size 10\n"
                "- IKEA dining table wooden 4 seats"
            )
        
        st.markdown(
            "**Tips for Better Results:**\n"
            "- Include brand names when known\n"
            "- Specify models, sizes, colors, and specifications\n"
            "- Use common product terminology\n"
            "- Be specific about electronics (storage, screen size, etc.)"
        )
    
    def _render_about_section(self) -> None:
        """Render about section with feature information."""
        st.markdown(
            "This tool helps insurance companies and individuals determine fair "
            "reimbursement values for lost or stolen items by finding current "
            "market prices for equivalent products.\n\n"
            "**Features:**\n"
            "- Smart item parsing and categorization\n"
            "- Real-time product search across multiple retailers\n"
            "- Current market pricing information\n"
            "- Confidence scoring for match quality\n"
            "- Direct links to purchase replacement items\n\n"
            "**Powered by:** Parallel AI's advanced search and research APIs"
        )


def main() -> None:
    """Main entry point for the Streamlit application."""
    app = InsuranceItemMatcherApp()
    app.run()


if __name__ == "__main__":
    main()