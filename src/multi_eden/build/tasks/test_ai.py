"""
AI testing task for running API tests against real AI models.

This task runs AI tests that require GEMINI_API_KEY to be set.
It bypasses the config-env layer for simpler local testing.
"""

import os
import sys
import subprocess
from invoke import task


@task(help={
    'verbose': 'Show verbose test output',
    'pattern': 'Test pattern to match (default: test_prompt_service)',
})
def ai(ctx, verbose=False, pattern='test_prompt_service'):
    """
    Run AI API tests against real models.
    
    Requirements:
    - GEMINI_API_KEY environment variable must be set
    
    Examples:
        ./invoke test ai
        ./invoke test ai --verbose
        ./invoke test ai --pattern=test_prompt
    
    Note: This bypasses config-env for simpler local testing.
    """
    
    # Check for required environment variable
    if not os.getenv('GEMINI_API_KEY'):
        print("❌ GEMINI_API_KEY environment variable is required for AI tests", file=sys.stderr)
        print("   Set it with: export GEMINI_API_KEY=your_api_key", file=sys.stderr)
        sys.exit(1)
    
    print("🤖 Running AI API tests...")
    print(f"   Pattern: {pattern}")
    print(f"   API Key: {'✅ Set' if os.getenv('GEMINI_API_KEY') else '❌ Missing'}")
    
    # Build test command
    cmd = [
        sys.executable, '-m', 'pytest',
        f'tests/api/{pattern}.py',
        '-v' if verbose else '-q',
        '--tb=short'
    ]
    
    # Run the tests
    try:
        result = subprocess.run(cmd, cwd=ctx.cwd or os.getcwd())
        if result.returncode == 0:
            print("✅ AI tests passed!")
        else:
            print("❌ AI tests failed!")
            sys.exit(result.returncode)
            
    except FileNotFoundError:
        print("❌ pytest not found. Install with: pip install pytest", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running AI tests: {e}", file=sys.stderr)
        sys.exit(1)
