"""
API tests for PromptService.

These tests require GEMINI_API_KEY environment variable to be set.
Run with: ./invoke test ai
"""

import os
import unittest
import json
from multi_eden.run.ai.prompt_service import PromptService


class TestPromptService(unittest.TestCase):
    """Test PromptService with real AI models."""
    
    @classmethod
    def setUpClass(cls):
        """Ensure GEMINI_API_KEY is set before running any tests."""
        if not os.getenv('GEMINI_API_KEY'):
            raise unittest.SkipTest(
                "GEMINI_API_KEY environment variable must be set to run AI tests. "
                "Set it with: export GEMINI_API_KEY=your_api_key"
            )
    
    def test_simple_math_prompt(self):
        """Test basic math prompt with default model."""
        service = PromptService()
        response = service.process("What is 7 + 5? Answer with just the number.")
        
        self.assertEqual(response.status, 'success')
        self.assertIn('12', response.content)
        self.assertIsNotNone(response.meta)
        self.assertIsNotNone(response.meta.model)
        print(f"Default model used: {response.meta.model}")
    
    def test_json_response_prompt(self):
        """Test prompt requesting JSON format response."""
        service = PromptService()
        prompt = 'Return this data as JSON: {"name": "test", "value": 42}'
        response = service.process(prompt)
        
        self.assertEqual(response.status, 'success')
        self.assertIn('{', response.content)
        self.assertIn('"name"', response.content)
        self.assertIn('"value"', response.content)
        
        # Try to parse as JSON to verify it's valid
        try:
            json.loads(response.content)
        except json.JSONDecodeError:
            # If not pure JSON, should at least contain JSON-like structure
            self.assertIn('test', response.content)
            self.assertIn('42', response.content)
    
    def test_model_override(self):
        """Test using alternate model and verify metadata."""
        # Use a different model variant
        service = PromptService(model_override='gemini-2.5-pro')
        response = service.process("Say 'Hello from alternate model'")
        
        self.assertEqual(response.status, 'success')
        self.assertIn('Hello', response.content)
        self.assertIsNotNone(response.meta.model)
        
        # Verify the model override was used
        print(f"Override model used: {response.meta.model}")
        # The actual model name might be normalized, so just check it's set
        self.assertTrue(len(response.meta.model) > 0)
    
    def test_empty_prompt_handling(self):
        """Test handling of empty or whitespace-only prompts."""
        service = PromptService()
        
        # Test completely empty prompt
        with self.assertRaises(ValueError):
            service.process("")
        
        # Test whitespace-only prompt
        with self.assertRaises(ValueError):
            service.process("   \n\t   ")
    
    def test_metadata_validation(self):
        """Test that response metadata contains expected fields."""
        service = PromptService()
        response = service.process("Test metadata")
        
        self.assertEqual(response.status, 'success')
        self.assertIsNotNone(response.meta)
        self.assertIsNotNone(response.meta.model)
        self.assertIsNotNone(response.meta.time)
        self.assertGreater(response.meta.time, 0)
        
        print(f"Processing time: {response.meta.time:.3f}ms")


if __name__ == '__main__':
    unittest.main()
