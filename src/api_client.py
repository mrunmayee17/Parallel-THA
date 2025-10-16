"""Parallel AI API client for the Insurance Item Matcher service."""

import time
import logging
from typing import Dict, Any, List, Optional

try:
    from parallel import Parallel
    from parallel.types import TaskSpecParam
except ImportError:
    raise ImportError("Please install the parallel-web package: pip install parallel-web")

from .config import Config
from .models import APIError


logger = logging.getLogger(__name__)


class ParallelAIClient:
    """Client for interacting with Parallel AI APIs using the official SDK."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Parallel AI client.
        
        Args:
            api_key: Optional API key. If not provided, uses config default.
        """
        self.api_key = api_key or Config.PARALLEL_AI_API_KEY
        
        if not self.api_key:
            raise ValueError("API key is required. Set PARALLEL_AI_API_KEY environment variable or provide api_key parameter.")
        
        try:
            self.client = Parallel(api_key=self.api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Parallel client: {e}")
            raise APIError(f"Failed to initialize Parallel AI client: {str(e)}")
    
    def search(self, objective: str, search_queries: Optional[List[str]] = None, max_results: Optional[int] = None, max_chars_per_result: Optional[int] = None, processor: Optional[str] = None) -> Dict[str, Any]:
        """Perform a search using the Search API.
        
        Args:
            objective: Natural language description of what you want to find
            search_queries: Optional specific search queries
            max_results: Maximum number of results to return
            max_chars_per_result: Maximum characters per result
            processor: Processor type (base or pro)
            
        Returns:
            Search results from the API
        """
        try:
            logger.debug(f"Performing search with objective: {objective[:100]}...")
            
            # Prepare search parameters
            search_params = {
                "objective": objective,
                "processor": processor or "base",
                "max_results": max_results or Config.MAX_RESULTS,
                "max_chars_per_result": max_chars_per_result or Config.MAX_CHARS_PER_RESULT
            }
            
            if search_queries:
                search_params["search_queries"] = search_queries
            
            # Use the beta search API
            search_result = self.client.beta.search(**search_params)
            
            logger.debug(f"Search completed successfully")
            return {"results": search_result.results}
            
        except Exception as e:
            logger.error(f"Search API error: {str(e)}")
            # Check if it's an authentication error
            if "401" in str(e) or "unauthorized" in str(e).lower() or "invalid" in str(e).lower():
                raise APIError(f"Authentication failed: {str(e)}", status_code=401)
            else:
                raise APIError(f"Search request failed: {str(e)}")
    
    def create_task(self, input_text: str, output_schema: str, processor: Optional[str] = None) -> Dict[str, Any]:
        """Create and run a task using the Task Run API.
        
        Args:
            input_text: Input text for the task
            output_schema: Description of the desired output format
            processor: Processor type (base, pro, or ultra)
            
        Returns:
            Task result
        """
        try:
            logger.debug(f"Creating task with input: {input_text[:100]}...")
            
            # Create task run
            task_run = self.client.task_run.create(
                input=input_text,
                task_spec=TaskSpecParam(output_schema=output_schema),
                processor=processor or "base"
            )
            
            logger.debug(f"Task created with run ID: {task_run.run_id}")
            
            # Get the result (this will wait for completion)
            run_result = self.client.task_run.result(task_run.run_id, api_timeout=100)  # 5 minute timeout
            
            logger.debug("Task completed successfully")
            return {"output": run_result.output, "run_id": task_run.run_id}
            
        except Exception as e:
            logger.error(f"Task API error: {str(e)}")
            # Check if it's an authentication error
            if "401" in str(e) or "unauthorized" in str(e).lower() or "invalid" in str(e).lower():
                raise APIError(f"Authentication failed: {str(e)}", status_code=401)
            else:
                raise APIError(f"Task request failed: {str(e)}")
