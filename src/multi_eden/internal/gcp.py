"""
Multi-Environment SDK Core Functions

Generic, reusable functions for multi-environment configuration management.
No project-specific code - completely domain-agnostic.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, List

from multi_eden.run.config.testing import is_test_mode
def verify_gcp_connectivity(project_id: str) -> bool:
    """
    Verify GCP connectivity and project access.
    
    Args:
        project_id: GCP Project ID to verify
        
    Returns:
        True if accessible, False otherwise
        
    Raises:
        RuntimeError: If gcloud is not configured
    """
    try:
        # Check if gcloud is configured
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"], 
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            raise RuntimeError("gcloud not configured. Run 'gcloud auth login' first.")
        
        # Verify we can access the specified project
        result = subprocess.run(
            ["gcloud", "projects", "describe", project_id], 
            capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            return False
            
        return True
        
    except Exception as e:
        raise RuntimeError(f"Error verifying GCP access: {e}")


def get_project_label(project_id: str, label_key: str) -> Optional[str]:
    """
    Get a project label value.
    
    Args:
        project_id: GCP Project ID
        label_key: Label key to retrieve
        
    Returns:
        Label value if found, None otherwise
    """
    try:
        result = subprocess.run(
            ["gcloud", "projects", "describe", project_id, 
             f"--format=value(labels.{label_key})"], 
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
        
    except Exception:
        return None


def verify_bucket_access(bucket_name: str) -> bool:
    """
    Verify access to a GCS bucket.
    
    Args:
        bucket_name: GCS bucket name (without gs:// prefix)
        
    Returns:
        True if accessible, False otherwise
    """
    try:
        result = subprocess.run(
            ["gsutil", "ls", f"gs://{bucket_name}"], 
            capture_output=True, text=True, check=False
        )
        return result.returncode == 0
        
    except Exception:
        return False


def check_bucket_exists_and_ownership(bucket_name: str, expected_project_id: str) -> tuple[bool, bool, Optional[str]]:
    """
    Check if a bucket exists and verify its project ownership.
    
    This function enforces a critical architectural constraint: the config bucket MUST belong
    to the target project specified in the local .config-project file. This is required to
    support the multi-env-sdk's core design principle of having a single local config file
    with just the project ID as the only prerequisite for fully automated configuration
    management across multiple environments.
    
    Key architectural reasons for this constraint:
    1. **Single Source of Truth**: The project ID in .config-project is the "master key"
       that unlocks all configuration management operations
    2. **Automated Bucket Management**: Operations like enabling versioning, setting IAM
       policies, and lifecycle rules require the project ID that owns the bucket
    3. **Multi-Environment Support**: The same project ID must control the bucket for
       consistent deployment across dev, staging, and production environments
    4. **Security and Isolation**: Prevents accidental cross-project bucket usage that
       could lead to configuration leaks or permission issues
    
    Args:
        bucket_name: GCS bucket name (without gs:// prefix)
        expected_project_id: Expected GCP project ID that should own the bucket
        
    Returns:
        Tuple of (bucket_exists, accessible, actual_project_id)
        - bucket_exists: True if bucket exists
        - accessible: True if we can access the bucket
        - actual_project_id: Project ID that owns the bucket (None if not accessible)
    """
    try:
        # First check if we can access the bucket at all
        result = subprocess.run(
            ["gsutil", "ls", "-L", f"gs://{bucket_name}"], 
            capture_output=True, text=True, check=False
        )
        
        if result.returncode != 0:
            # Bucket doesn't exist or we can't access it
            return False, False, None
        
        # Bucket exists and is accessible, now check ownership
        result = subprocess.run(
            ["gsutil", "ls", "-L", f"gs://{bucket_name}", "--format=value(project_number)"], 
            capture_output=True, text=True, check=False
        )
        
        if result.returncode == 0:
            actual_project_number = result.stdout.strip()
            
            # Convert project number to project ID for comparison
            # We need to get the project ID from the project number
            result = subprocess.run(
                ["gcloud", "projects", "list", f"--filter=projectNumber={actual_project_number}", "--format=value(project_id)"], 
                capture_output=True, text=True, check=False
            )
            
            if result.returncode == 0:
                actual_project_id = result.stdout.strip()
                return True, True, actual_project_id
        
        # If we can access but can't determine ownership, assume it's accessible
        return True, True, None
        
    except Exception:
        return False, False, None


def create_gcs_bucket(project_id: str, bucket_name: str, location: str = "US") -> bool:
    """
    Create a GCS bucket with versioning enabled.
    
    Args:
        project_id: GCP Project ID
        bucket_name: GCS bucket name
        location: GCS bucket location
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"  🔧 Creating bucket: {bucket_name}")
        # Create bucket
        result = subprocess.run(
            ["gsutil", "mb", "-p", project_id, f"gs://{bucket_name}"], 
            capture_output=True, text=True, check=False
        )
        print(f"  📊 Create bucket result: {result.returncode}")
        if result.returncode != 0:
            print(f"  ❌ Create bucket failed: {result.stderr}")
            return False
        
        print(f"  🔧 Enabling versioning for: {bucket_name}")
        # Enable versioning
        result = subprocess.run(
            ["gsutil", "versioning", "set", "on", f"gs://{bucket_name}"], 
            capture_output=True, text=True, check=False
        )
        print(f"  📊 Versioning result: {result.returncode}")
        if result.returncode != 0:
            print(f"  ❌ Versioning failed: {result.stderr}")
            return False
        
        print(f"  ✅ Bucket creation and versioning successful")
        return True
        
    except Exception as e:
        print(f"  ❌ Exception in create_gcs_bucket: {e}")
        return False


def find_config_bucket(project_id: str, label_key: str) -> Optional[str]:
    """
    Find a GCS bucket in the project that has the specified label indicating it's a config bucket.
    
    Args:
        project_id: GCP Project ID to search in
        label_key: Label key to look for (e.g., "multi-env-sdk-config-bucket")
        
    Returns:
        Bucket name if found, None otherwise
    """
    try:
        # List all buckets in the project with labels
        result = subprocess.run(
            ["gsutil", "ls", "-L", "-p", project_id], 
            capture_output=True, text=True, check=False
        )
        
        if result.returncode != 0:
            return None
            
        # Parse the output to find buckets with the config label
        current_bucket = None
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('gs://'):
                # Extract bucket name from gs://bucket-name/
                current_bucket = line.replace('gs://', '').rstrip('/')
            elif line.startswith('Labels:') and current_bucket:
                # Check if this bucket has the config label
                labels_line = line.replace('Labels:', '').strip()
                if label_key in labels_line:
                    return current_bucket
                    
        return None
        
    except Exception as e:
        print(f"Error finding config bucket: {e}")
        return None


def find_config_buckets_by_label(project_id: str, label_key: str, label_value: str) -> List[str]:
    """
    Find all GCS buckets in the project that have the specified label with the given value.
    
    Args:
        project_id: GCP Project ID to search in
        label_key: Label key to look for (e.g., "multi-env-sdk")
        label_value: Label value to match (e.g., "config")
        
    Returns:
        List of bucket names that match the label criteria
    """
    try:
        print(f"    🔍 Searching for buckets with label {label_key}:{label_value} in project {project_id}")
        print(f"    📋 Running: gsutil ls -L -p {project_id}")
        print(f"    ⏱️  Starting gsutil command...")
        
        # List all buckets in the project with labels
        result = subprocess.run(
            ["gsutil", "ls", "-L", "-p", project_id], 
            capture_output=True, text=True, check=True, timeout=30
        )
        
        print(f"    ✅ gsutil command completed successfully")
        print(f"    📊 Parsing output...")
        
        # Count total buckets processed for logging
        total_buckets = len([line for line in result.stdout.split('\n') if line.startswith('gs://')])
        print(f"    📊 TOTAL BUCKETS IN PROJECT: {total_buckets}")
        
        # Check if we're in a test environment and enforce bucket limits
        try:
            # Only import and check if we're running tests (avoid circular imports in production)
            if 'pytest' in sys.modules or is_test_mode():
                from ..tests.config import MAX_EXPECTED_BUCKETS
                if total_buckets > MAX_EXPECTED_BUCKETS:
                    print(f"    ⚠️  WARNING: Bucket count ({total_buckets}) exceeds expected maximum ({MAX_EXPECTED_BUCKETS})")
                    print(f"    💡 Consider cleaning up unused buckets to avoid accumulation")
                    # Note: This is a warning, not an error, to avoid breaking existing tests
                    # but it will help developers notice bucket accumulation issues
        except ImportError:
            # Not in test environment, skip the check
            pass
        # Parse the output to find buckets with the config label and matching value
        matching_buckets = []
        current_bucket = None
        in_labels_section = False
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('gs://'):
                # Extract bucket name from gs://bucket-name/
                # Handle both "gs://bucket-name/" and "gs://bucket-name/ :" formats
                bucket_part = line.replace('gs://', '').split()[0].rstrip('/')
                current_bucket = bucket_part
                in_labels_section = False
                print(f"    🪣 Processing bucket: {current_bucket}")
            elif line.startswith('Labels:') and current_bucket:
                in_labels_section = True
                print(f"    🏷️  Found labels section for bucket: {current_bucket}")
            elif in_labels_section and current_bucket:
                print(f"    🏷️  Checking label line: {line}")
                # Check if this line contains our label with the right value
                if f'"{label_key}": "{label_value}"' in line:
                    print(f"    ✅ Found matching label for bucket: {current_bucket}")
                    matching_buckets.append(current_bucket)
                    current_bucket = None  # Prevent duplicate adds
                elif line.startswith('Default KMS key:') or line.startswith('Time created:'):
                    # End of labels section
                    in_labels_section = False
                    print(f"    📝 End of labels section")
        
        print(f"    🎯 Found {len(matching_buckets)} matching buckets: {matching_buckets}")
        return matching_buckets
        
    except subprocess.TimeoutExpired:
        print(f"    ⏰ gsutil command timed out after 30 seconds")
        raise RuntimeError(f"gsutil command timed out while listing buckets in project {project_id}")
    except subprocess.CalledProcessError as e:
        print(f"    ❌ gsutil command failed with return code {e.returncode}")
        print(f"    ❌ stderr: {e.stderr}")
        raise RuntimeError(f"Failed to list buckets in project {project_id}: {e.stderr}")
    except Exception as e:
        print(f"    ❌ Unexpected error: {e}")
        raise RuntimeError(f"Error finding config buckets by label: {e}")


def write_config_file(file_path: str, content: str) -> bool:
    """
    Write content to a configuration file.
    
    Args:
        file_path: Path to the configuration file
        content: Content to write
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(file_path, "w") as f:
            f.write(content)
        return True
        
    except Exception:
        return False


def set_project_label(project_id: str, label_key: str, label_value: str) -> bool:
    """
    Set a project label.
    
    Args:
        project_id: GCP Project ID
        label_key: Label key to set
        label_value: Label value to set
        
    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["gcloud", "projects", "add-labels", project_id, 
             f"--labels={label_key}={label_value}"], 
            capture_output=True, text=True, check=False
        )
        return result.returncode == 0
        
    except Exception:
        return False


def update_gitignore(gitignore_path: str, entry: str) -> bool:
    """
    Add an entry to .gitignore if it doesn't exist.
    
    Args:
        gitignore_path: Path to .gitignore file
        entry: Entry to add
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if Path(gitignore_path).exists():
            with open(gitignore_path, "r") as f:
                content = f.read()
            
            if entry not in content:
                with open(gitignore_path, "a") as f:
                    f.write(f"\n# Configuration project ID\n{entry}\n")
        else:
            with open(gitignore_path, "w") as f:
                f.write(f"# Configuration project ID\n{entry}\n")
        
        return True
        
    except Exception:
        return False


def get_cloud_run_service_url(project_id: str, service_name: str, region: str = "us-central1") -> str:
    """
    Get the URL of a Cloud Run service.
    
    Args:
        project_id: GCP Project ID
        service_name: Cloud Run service name
        region: GCP region (default: us-central1)
        
    Returns:
        Cloud Run service URL
        
    Raises:
        RuntimeError: If service not found or gcloud command fails
    """
    try:
        result = subprocess.run(
            ["gcloud", "run", "services", "describe", service_name,
             "--project", project_id, "--region", region, 
             "--format=value(status.url)"],
            capture_output=True, text=True, check=True
        )
        
        service_url = result.stdout.strip()
        if not service_url:
            raise RuntimeError(f"Cloud Run service '{service_name}' in project '{project_id}' has no URL")
            
        return service_url
        
    except subprocess.CalledProcessError as e:
        stderr_output = e.stderr.strip() if e.stderr else "No error details"
        raise RuntimeError(f"Failed to get Cloud Run service URL for '{service_name}' in project '{project_id}': {stderr_output}")
    except Exception as e:
        raise RuntimeError(f"Error retrieving Cloud Run service URL: {e}")



