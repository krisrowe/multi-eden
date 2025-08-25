"""Test runner for multi-env SDK integration tests."""

import subprocess
import sys
from pathlib import Path


def run_integration_tests(verbose=False):
    """
    Run integration tests for the multi-env SDK.
    
    Args:
        verbose: Enable verbose output (-v flag for pytest)
        
    Returns:
        bool: True if all tests passed, False otherwise
    """
    # Get the tests directory
    tests_dir = Path(__file__).parent / "tests"
    
    # Check if test configuration exists
    try:
        sys.path.insert(0, str(tests_dir))
        from config import get_test_project_id
        project_id = get_test_project_id()
        print(f"🧪 Running SDK integration tests against project: {project_id}")
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ Cannot run tests: {e}")
        print("💡 Configure project ID in .config-project file")
        print("   Example: echo 'my-test-project-123' > .config-project")
        return False
    
    # Build pytest command
    cmd = [sys.executable, "-m", "pytest", str(tests_dir / "test_config_init.py")]
    if verbose:
        cmd.append("-v")
    
    # Run tests
    try:
        result = subprocess.run(cmd, cwd=str(Path(__file__).parent))
        if result.returncode == 0:
            print("✅ All SDK tests passed!")
            return True
        else:
            print("❌ Some SDK tests failed")
            return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


def test_sdk(ctx, verbose=False):
    """
    Run integration tests for the multi-env SDK.
    
    Args:
        verbose: Enable verbose output (-v flag for pytest)
    """
    return run_integration_tests(verbose)
