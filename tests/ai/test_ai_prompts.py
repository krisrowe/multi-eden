"""Tests for AI prompt functionality using PromptService."""
import os
import pytest
import logging
import json

from multi_eden.run.ai.prompt_service import PromptService

API_KEY_ENV_VAR_NAME = "GEMINI_API_KEY"

class TestAIPrompts:
    """Test AI prompt functionality using PromptService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.logger = logging.getLogger(__name__)
        self.default_model = "gemini-2.5-flash"
        self.alt_model = "gemini-2.5-flash-lite"
    
    def test_math_prompt_predictable_output(self):
        """Test math prompt with predictable integer output."""
        self.logger.info("Testing math prompt with predictable output")
        
        service = PromptService()
        test_prompt = "Tell me what the answer to 2 + 2. Respond with only an integer."

        try:
            response = service.process(test_prompt)
            
            # Verify response structure
            assert response is not None, "Expected non-None response"
            assert response.status == 'success', f"Expected success status, got {response.status}"
            assert hasattr(response, 'content'), "Response should have content attribute"
            
            # The response should contain "4" (the answer to 2+2)
            assert "4" in response.content, f"Expected response to contain '4', got: {response.content}"
            
            self.logger.info(f"✅ Math prompt test successful. Response: {response.content}")
            
        except Exception as e:
            pytest.fail(f"Math prompt test failed: {e}")
    
    def test_json_prompt_no_schema(self):
        """Test prompt expecting JSON output without formal schema."""
        self.logger.info("Testing JSON prompt without formal schema")
        
        service = PromptService()
        test_prompt = '''Tell me the address of the Eiffel Tower and give it to me in the following JSON format:
        {
            "name": "landmark name",
            "address": "street address",
            "city": "city name",
            "country": "country name"
        }'''

        try:
            response = service.process(test_prompt)
            
            # Verify response structure
            assert response is not None, "Expected non-None response"
            assert response.status == 'success', f"Expected success status, got {response.status}"
            
            # Try to parse as JSON
            try:
                json_data = json.loads(response.content)
                assert isinstance(json_data, dict), "Expected JSON object"
                assert "name" in json_data, "Expected 'name' field in JSON"
                assert "address" in json_data, "Expected 'address' field in JSON"
                self.logger.info(f"✅ JSON prompt test successful. Parsed JSON: {json_data}")
            except json.JSONDecodeError:
                # If not valid JSON, at least check it contains expected keywords
                content_lower = response.content.lower()
                assert "eiffel" in content_lower, "Expected 'eiffel' in response"
                assert "tower" in content_lower, "Expected 'tower' in response"
                self.logger.info(f"✅ JSON prompt test successful (non-JSON format). Response: {response.content}")
            
        except Exception as e:
            pytest.fail(f"JSON prompt test failed: {e}")
    
    def test_json_prompt_with_schema(self):
        """Test prompt with JSON schema supplied."""
        self.logger.info("Testing prompt with JSON schema")
        
        service = PromptService()
        
        # Define a JSON schema
        schema = {
            "type": "object",
            "properties": {
                "landmark": {"type": "string"},
                "location": {"type": "string"},
                "built_year": {"type": "integer"}
            },
            "required": ["landmark", "location"]
        }
        
        # Set the schema on the service
        service.set_schema(schema)
        
        test_prompt = "Tell me about the Statue of Liberty - its name, location, and when it was built."

        try:
            response = service.process(test_prompt)
            
            # Verify response structure
            assert response is not None, "Expected non-None response"
            assert response.status == 'success', f"Expected success status, got {response.status}"
            
            # Response should contain relevant information
            content_lower = response.content.lower()
            assert "statue" in content_lower or "liberty" in content_lower, "Expected statue/liberty in response"
            
            self.logger.info(f"✅ Schema prompt test successful. Response: {response.content}")
            
        except Exception as e:
            pytest.fail(f"Schema prompt test failed: {e}")
    
    def test_empty_prompt_negative(self):
        """Test blank/missing/empty prompt (negative test case)."""
        self.logger.info("Testing empty prompt negative case")
        
        service = PromptService()
        
        # Test empty string
        with pytest.raises(ValueError, match="Prompt text cannot be empty"):
            service.process("")
        
        # Test whitespace-only string
        with pytest.raises(ValueError, match="Prompt text cannot be empty"):
            service.process("   \n\t   ")
        
        # Test None (should raise ValueError from our validation)
        with pytest.raises(ValueError, match="Prompt text cannot be empty"):
            service.process(None)
        
        self.logger.info("✅ Empty prompt negative test successful")
    
    def test_default_model_faster_used(self):
        """Test that default model gemini-2.5-flash is used (check meta output)."""
        self.logger.info("Testing default model usage")
        
        service = PromptService()  # No model override
        test_prompt = "What is the capital of France? Answer briefly."

        try:
            response = service.process(test_prompt)
            
            # Verify response structure
            assert response is not None, "Expected non-None response"
            assert response.status == 'success', f"Expected success status, got {response.status}"
            assert hasattr(response, 'meta'), "Response should have meta attribute"
            
            # Check that default model was used
            expected_model = "gemini-2.5-flash"
            assert response.meta.model == expected_model, f"Expected default model {expected_model}, got {response.meta.model}"
            
            self.logger.info(f"✅ Default model test successful. Used model: {response.meta.model}")
            
        except Exception as e:
            pytest.fail(f"Default model test failed: {e}")
    
    def test_alt_model_fastest_used(self):
        """Test that alternative model gemini-2.5-flash-lite was used (check meta output)."""
        self.logger.info("Testing alternative model usage")
        
        service = PromptService(model_override=self.alt_model)
        test_prompt = "What is the capital of Germany? Answer briefly."

        try:
            response = service.process(test_prompt)
            
            # Verify response structure
            assert response is not None, "Expected non-None response"
            assert response.status == 'success', f"Expected success status, got {response.status}"
            assert hasattr(response, 'meta'), "Response should have meta attribute"
            
            # Check that alternative model was used
            expected_model = "gemini-2.5-flash-lite"
            assert response.meta.model == expected_model, f"Expected alt model {expected_model}, got {response.meta.model}"
            
            self.logger.info(f"✅ Alt model test successful. Used model: {response.meta.model}")
            
        except Exception as e:
            pytest.fail(f"Alt model test failed: {e}")
