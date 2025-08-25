"""
Tests for Gemini AI client functionality.
"""
import os
import pytest
import logging

from multi_eden.run.ai.gemini_client import GeminiClient

API_KEY_ENV_VAR_NAME = "GEMINI_API_KEY"

class TestGeminiClient:
    """Test the Gemini AI client functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.logger = logging.getLogger(__name__)
        self.service_name = None  # No service name - test raw LLM functionality
        self.model_name = "gemini-1.5-flash"
    
    @pytest.mark.skipif(
        not os.getenv(API_KEY_ENV_VAR_NAME),
        reason=f"{API_KEY_ENV_VAR_NAME} environment variable not set - skipping real API test"
    )
    @pytest.mark.integration
    def test_prompt(self):
        """Test real API call to Gemini with a simple, predictable prompt."""
        self.logger.info("Testing real Gemini API call with simple prompt")
        
        # Create the client - it will get the API key from the environment automatically
        client = GeminiClient(model_name=self.model_name, service_name=self.service_name)

        test_prompt = "What is 2 + 2? Answer with just the number."

        try:
            result = client._process_prompt(test_prompt)
            
            # Verify we got a response
            assert result is not None, "Expected non-None result from Gemini API"
            assert isinstance(result, str), f"Expected string result, got {type(result)}"
            
            # The response should contain "4" somewhere (the answer to 2+2)
            assert "4" in result, f"Expected response to contain '4', got: {result}"
            
            self.logger.info(f"✅ Gemini API test successful. Response: {result}")
            
        except Exception as e:
            pytest.fail(f"Gemini API call failed: {e}")

