"""
Mock Gemini client for testing and development.

Mimics Gemini API responses by loading pre-formatted responses from JSON files.
This client simulates how the real Gemini client would return data.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from .base_client import ModelClient

# Get logger from centralized logging
from multi_eden.run.config.logging import get_logger
logger = get_logger(__name__)


class MockGeminiClient(ModelClient):
    """Mock Gemini client that loads responses from JSON files.

    Used for testing and development without requiring real Gemini API access.
    Mimics Gemini's response format exactly, so no translation is needed.
    """

    def __init__(self, test_data_path: str, service_name: str):
        """Initialize the test client.

        Args:
            test_data_path: Path to directory containing test data JSON response files
            service_name: Name of the service
        """
        super().__init__(service_name)
        self.test_data_dir = Path(test_data_path)
        
        # Debug logging to see what path we're actually trying to access
        import os
        logger.debug(f"MockGeminiClient initialized with test data path: {test_data_path}")
        logger.debug(f"Resolved to absolute path: {self.test_data_dir.absolute()}")
        logger.debug(f"Current working directory: {os.getcwd()}")
        logger.debug(f"Path exists: {self.test_data_dir.exists()}")
        
        if not self.test_data_dir.exists():
            raise FileNotFoundError(f"Test data directory not found: {self.test_data_dir}")

        # Cache of loaded responses
        self._response_cache = {}

    def _process_prompt(self, formatted_prompt: str, function_declarations: Optional[List[Dict[str, Any]]] = None, 
                       callback: Optional[Callable] = None, **kwargs) -> Any:
        """Process a prompt by loading response from JSON file.

        Args:
            formatted_prompt: The complete formatted prompt (ignored in test mode)
            function_declarations: Optional function declarations (ignored in test mode)
            callback: Optional callback function to process response results
            **kwargs: Additional arguments (ignored in test mode)

        Returns:
            The result of the callback function execution if provided,
            otherwise the raw response loaded from JSON

        Raises:
            FileNotFoundError: If no response file is found for the prompt
            json.JSONDecodeError: If the response file contains invalid JSON
        """
        # Use the original user prompt for test data lookup
        user_prompt = self.get_original_prompt()
        if not user_prompt:
            raise ValueError("No original prompt available for test data lookup")
        
        # Try to find a matching response file using cases.yaml mapping
        cases_file = self.test_data_dir / "cases.yaml"
        if cases_file.exists():
            try:
                import yaml
                with open(cases_file, 'r') as f:
                    cases_map = yaml.safe_load(f)
                
                # Check if we have an exact prompt match
                if 'cases' in cases_map:
                    for case in cases_map['cases']:
                        if case.get('prompt') == user_prompt:
                            case_id = case.get('id')
                            if case_id:
                                response_file = self.test_data_dir / f"{case_id}.json"
                                
                                if response_file.exists():
                                    with open(response_file, 'r') as f:
                                        response = json.load(f)
                                        logger.debug(f"Found prompt mapping match: {response_file.name}")
                                        self._response_cache[user_prompt] = response
                                        return response
                                else:
                                    logger.warning(f"Case file {case_id}.json not found")
                            break
            except (yaml.YAMLError, IOError) as e:
                logger.warning(f"Failed to load cases.yaml: {e}")

        # No prompt mapping found - throw error
        logger.error(f"No test case found for prompt: '{user_prompt}'")
        raise FileNotFoundError(
            f"No test case found for prompt: '{user_prompt}'\n"
            f"Available test cases in {self.test_data_dir}/cases.yaml:\n"
            f"Add a new case or check the prompt spelling."
        )

    def clear_cache(self):
        """Clear the response cache."""
        self._response_cache.clear()
