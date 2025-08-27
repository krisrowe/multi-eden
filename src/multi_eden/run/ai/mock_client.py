"""
Mock AI client for testing purposes.
"""

from .base_client import ModelClient
from .test_data import get_unit_test_case_data
from typing import Any, Dict, List, Optional, Callable
import logging
import inspect

logger = logging.getLogger(__name__)


class MockClient(ModelClient):
    """Mock AI client that returns predefined responses for testing."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.operation = None
        self.test_case_id = "single-item-n-std-units"  # Default test case
    
    def set_operation(self, operation: str, test_case_id: str = "single-item-n-std-units"):
        """Set the operation context for loading appropriate test data."""
        self.operation = operation
        self.test_case_id = test_case_id
        logger.debug(f"MockClient configured for operation: {operation}, test_case: {test_case_id}")
    
    def _get_calling_service_operation(self):
        """Automatically detect the operation from the calling service class."""
        frame = inspect.currentframe()
        try:
            # Walk up the call stack to find a service with an operation attribute
            frame_count = 0
            while frame and frame_count < 10:  # Limit search depth
                frame = frame.f_back
                frame_count += 1
                if frame and 'self' in frame.f_locals:
                    caller_self = frame.f_locals['self']
                    class_name = caller_self.__class__.__name__
                    if hasattr(caller_self, 'operation'):
                        operation = caller_self.operation
                        # Only return non-None operations
                        if operation is not None:
                            logger.debug(f"MockClient detected operation '{operation}' from {class_name}")
                            return operation
        except Exception as e:
            logger.debug(f"Failed to detect calling service operation: {e}")
        finally:
            del frame
        logger.debug("No operation found in call stack")
        return None
    
    def _process_prompt(self, formatted_prompt: str, function_declarations: Optional[List[Dict[str, Any]]] = None,
                       callback: Optional[Callable] = None, **kwargs) -> Any:
        """Process the formatted prompt and return mock response from test data."""
        # Try to get operation from explicit setting or auto-detection
        operation = self.operation or self._get_calling_service_operation()
        logger.debug(f"MockClient processing prompt with operation: {operation}")
        
        if operation:
            try:
                # Check if this is whitespace-only input and use appropriate test case
                test_case_id = self.test_case_id
                if formatted_prompt and '"   "' in formatted_prompt:
                    test_case_id = "non-food-prompt"
                    logger.debug("MockClient detected whitespace-only input, using non-food-prompt test case")
                
                # Load llm-output test data for this operation (MockClient simulates AI response)
                test_data = get_unit_test_case_data(operation, "llm", test_case_id)
                logger.debug(f"MockClient loaded LLM test data for {operation}/{test_case_id}")
                return test_data
            except Exception as e:
                logger.warning(f"MockClient failed to load test data for {operation}/{self.test_case_id}: {e}")
                # Fall back to generic response
        
        # Fallback for when operation is not set or test data loading fails
        return {
            "status": "success",
            "message": "Mock response from MockClient",
            "prompt": formatted_prompt
        }

