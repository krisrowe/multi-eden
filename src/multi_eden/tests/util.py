"""
Utility functions for config sync tests.
Shared helper methods used by multiple test modules.
"""

# Test constants
LABEL_KEY = "multi-env-sdk"
LABEL_VALUE = "config"
TEST_APP_ID_BASE = "app"

# Import bucket limits from config
try:
    from .config import MAX_EXPECTED_BUCKETS
except ImportError:
    # Fallback value if config import fails
    MAX_EXPECTED_BUCKETS = 20

import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Callable

from ..internal import gcp
from .. import deploy


def generate_random_hash() -> str:
    """Generate a random hash for each test method."""
    return secrets.token_hex(4)


def generate_test_app_id(hash_suffix: str) -> str:
    """Generate a test app ID using app-hash format."""
    return f"app-{hash_suffix}"


def generate_default_bucket_name(project_id: str, app_id: str) -> str:
    """Generate the default bucket name using project-id-app-id-config format."""
    return f"{project_id}-{app_id}-config"


def generate_custom_bucket_name(project_id: str, app_id: str, custom_suffix: str = "custom") -> str:
    """Generate a custom bucket name using project-id-app-id-custom format."""
    return f"{project_id}-{app_id}-{custom_suffix}"


def get_test_project_id() -> str:
    """Get the test project ID from .config-project file."""
    config_file = Path(".config-project")
    if not config_file.exists():
        raise FileNotFoundError(".config-project file not found")
    
    project_id = config_file.read_text().strip()
    if not project_id:
        raise ValueError("Project ID is empty in .config-project file")
    
    return project_id


def create_test_context() -> Dict[str, Any]:
    """
    Create test context with project_id, app_ids, and bucket names.
    Ensures clean state at start - test fails if cleanup fails.
    """
    try:
        project_id = get_test_project_id()
    except (FileNotFoundError, ValueError) as e:
        raise RuntimeError(f"Test project not configured: {e}")
    
    # Generate primary app_id
    primary_hash = generate_random_hash()
    app_id = generate_test_app_id(primary_hash)
    
    # Generate secondary app_id for conflict testing
    secondary_hash = generate_random_hash()
    secondary_app_id = generate_test_app_id(secondary_hash)
    
    context = {
        # Project info
        'project_id': project_id,
        
        # Primary app
        'app_id': app_id,
        'hash': primary_hash,
        'default_bucket': f"{app_id}-config",
        'custom_bucket': lambda suffix: generate_custom_bucket_name(project_id, app_id, suffix),
        
        # Secondary app (for conflict tests)
        'secondary_app_id': secondary_app_id,
        'secondary_hash': secondary_hash,
        'secondary_default_bucket': f"{secondary_app_id}-config",
        'secondary_custom_bucket': lambda suffix: generate_custom_bucket_name(project_id, secondary_app_id, suffix),
    }
    
    return context


def ensure_clean_project_state(project_id: str) -> None:
    """Ensure no config buckets exist at the start of each test."""
    print(f"🔍 Ensuring no config buckets exist in project: {project_id}")
    
    # Find all buckets with config label
    existing_buckets = gcp.find_config_buckets_by_label(project_id, LABEL_KEY, LABEL_VALUE)
    
    if existing_buckets:
        print(f"⚠️  WARNING: Found {len(existing_buckets)} existing config buckets: {existing_buckets}")
        print(f"🧹 Initiating cleanup...")
        _clear_config_buckets(project_id)
        
        # Verify cleanup was successful
        remaining_buckets = gcp.find_config_buckets_by_label(project_id, LABEL_KEY, LABEL_VALUE)
        if remaining_buckets:
            print(f"❌ ERROR: Cleanup failed, still have {len(remaining_buckets)} config buckets: {remaining_buckets}")
            raise RuntimeError(f"Failed to clean project state: {len(remaining_buckets)} config buckets remain: {remaining_buckets}")
        else:
            print(f"✅ Cleanup successful, no config buckets remain")
    else:
        print(f"✅ Project is clean, no config buckets found")


def _clear_config_buckets(project_id: str) -> None:
    """Remove config labels from all buckets found in the project."""
    print(f"🔍 Clearing config labels from all buckets in project: {project_id}")
    
    try:
        # Find all buckets with config label
        existing_buckets = gcp.find_config_buckets_by_label(project_id, LABEL_KEY, LABEL_VALUE)
        print(f"🧹 Found {len(existing_buckets)} buckets with config labels: {existing_buckets}")
        
        for bucket in existing_buckets:
            print(f"🏷️  Removing config label from bucket: {bucket}")
            try:
                # Remove the specific label
                result = subprocess.run([
                    "gsutil", "label", "ch", 
                    f"-d", f"{LABEL_KEY}",
                    f"gs://{bucket}"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    print(f"✅ Successfully removed config label from: {bucket}")
                else:
                    print(f"❌ Failed to remove config label from {bucket}: {result.stderr}")
            except Exception as e:
                print(f"❌ Error removing label from {bucket}: {e}")
                
    except Exception as e:
        print(f"❌ Error during bucket cleanup: {e}")


def cleanup_test_buckets(project_id: str, *bucket_names: str) -> None:
    """Clean up specific test buckets at the end of each test."""
    print(f"🧹 Cleaning up test buckets: {bucket_names}")
    
    for bucket_name in bucket_names:
        if not bucket_name:
            continue
            
        print(f"🗑️  Cleaning up bucket: {bucket_name}")
        
        # Check if bucket exists before attempting cleanup
        check_result = subprocess.run([
            "gsutil", "ls", f"gs://{bucket_name}"
        ], capture_output=True, text=True, timeout=10)
        
        if check_result.returncode != 0:
            print(f"ℹ️  Bucket {bucket_name} not found (already cleaned up or never created)")
            continue
        
        print(f"✅ Found bucket {bucket_name}, proceeding with cleanup")
        
        # Remove all objects first
        print(f"🗑️  Removing objects from gs://{bucket_name}/*")
        result1 = subprocess.run([
            "gsutil", "-m", "rm", "-r", f"gs://{bucket_name}/*"
        ], capture_output=True, text=True, timeout=30)
        
        if result1.returncode == 0:
            print(f"✅ Objects removed from {bucket_name}")
        elif "No URLs matched" in result1.stderr:
            print(f"ℹ️  No objects to remove from {bucket_name}")
        else:
            print(f"⚠️  Object removal result: {result1.returncode} - {result1.stderr}")
        
        # Remove bucket
        print(f"🗑️  Removing bucket gs://{bucket_name}")
        result2 = subprocess.run([
            "gsutil", "rb", f"gs://{bucket_name}"
        ], capture_output=True, text=True, timeout=30)
        
        if result2.returncode == 0:
            print(f"✅ Bucket {bucket_name} removed successfully")
        else:
            print(f"❌ Failed to remove bucket {bucket_name}: {result2.stderr}")
            # Don't catch this error - let test fail if cleanup fails
    
    print(f"🧹 Test bucket cleanup completed")


def create_ephemeral_config_dir() -> Path:
    """Create an ephemeral directory for config files that will be automatically cleaned up."""
    temp_dir = tempfile.mkdtemp(prefix="test-config-")
    config_dir = Path(temp_dir) / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Created ephemeral config directory: {config_dir}")
    return config_dir


def create_dummy_config_files(config_dir: Path, env: str) -> None:
    """Create dummy config files for testing."""
    # Create dummy secrets.json
    secrets_file = config_dir / "secrets.json"
    secrets_content = {
        "env": env,
        "test_secret": "dummy-secret-value",
        "api_key": "dummy-api-key-12345"
    }
    secrets_file.write_text(str(secrets_content).replace("'", '"'))
    
    # Create dummy providers.json
    providers_file = config_dir / "providers.json"
    providers_content = {
        "env": env,
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "test_db"
        },
        "cache": {
            "redis_host": "127.0.0.1",
            "redis_port": 6379
        }
    }
    providers_file.write_text(str(providers_content).replace("'", '"'))
    
    # Create dummy host.json
    host_file = config_dir / "host.json"
    host_content = {
        "env": env,
        "domain": f"test-{env}.example.com",
        "ssl": True,
        "port": 443
    }
    host_file.write_text(str(host_content).replace("'", '"'))
    
    print(f"📝 Created dummy config files in {config_dir}: secrets.json, providers.json, host.json")


def verify_config_files_in_bucket(bucket_name: str, env: str) -> bool:
    """Verify that config files exist in the specified bucket for the given environment."""
    try:
        # Check if files exist in the bucket
        result = subprocess.run([
            "gsutil", "ls", f"gs://{bucket_name}/{env}/"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            print(f"❌ Could not list files in bucket {bucket_name}/{env}/")
            return False
        
        files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        required_files = [f"gs://{bucket_name}/{env}/secrets.json", 
                         f"gs://{bucket_name}/{env}/providers.json", 
                         f"gs://{bucket_name}/{env}/host.json"]
        
        missing_files = [f for f in required_files if f not in files]
        
        if missing_files:
            print(f"❌ Missing files in bucket: {missing_files}")
            return False
        
        print(f"✅ All required config files found in bucket {bucket_name}/{env}/")
        return True
        
    except Exception as e:
        print(f"❌ Error verifying config files: {e}")
        return False


def verify_config_files_in_local_dir(config_dir: Path, env: str) -> bool:
    """Verify that config files exist in the local directory for the given environment."""
    required_files = ["secrets.json", "providers.json", "host.json"]
    
    for filename in required_files:
        file_path = config_dir / filename
        if not file_path.exists():
            print(f"❌ Missing local file: {file_path}")
            return False
    
    print(f"✅ All required config files found in local directory {config_dir}")
    return True
