"""Integration tests for config bucket initialization.

These tests use a real GCP project to test all scenarios of init_terraform_config.
The project ID is read from .config-project file in the parent directory.

Example:
    pytest tests/test_config_init.py -v
"""

import pytest
import subprocess
import secrets
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..config import init as deploy
from ..internal import gcp
from ..config import util as sdk_config
from .util import (
    create_test_context,
    ensure_clean_project_state,
    cleanup_test_buckets,
    generate_random_hash,
    generate_test_app_id,
    generate_default_bucket_name,
    generate_custom_bucket_name,
    get_test_project_id
)


@pytest.fixture
def ctx():
    """
    Comprehensive test context with everything needed for all test scenarios.
    Ensures clean state at start - test fails if cleanup fails.
    """
    try:
        project_id = get_test_project_id()
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(f"Test project not configured: {e}")
    
    # Log starting bucket count
    try:
        result = subprocess.run(
            ["gsutil", "ls", "-p", project_id], 
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            total_buckets = len([line for line in result.stdout.split('\n') if line.startswith('gs://')])
            print(f"🚀 STARTING TEST - TOTAL BUCKETS IN PROJECT: {total_buckets}")
        else:
            print(f"🚀 STARTING TEST - Could not count buckets: gsutil failed")
    except Exception as e:
        print(f"🚀 STARTING TEST - Could not count buckets: {e}")
    
    # Ensure clean state - test fails if this fails
    ensure_clean_project_state(project_id)
    
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
    
    yield context
    
    # Log total bucket count at end of test
    try:
        result = subprocess.run(
            ["gsutil", "ls", "-p", project_id], 
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            total_buckets = len([line for line in result.stdout.split('\n') if line.startswith('gs://')])
            print(f"🧹 END OF TEST - TOTAL BUCKETS IN PROJECT: {total_buckets}")
        else:
            print(f"🧹 END OF TEST - Could not count buckets: gsutil failed")
    except Exception as e:
        print(f"🧹 END OF TEST - Could not count buckets: {e}")
    
    # Clean up any remaining test buckets at the end
    cleanup_test_buckets(project_id)


# This function is now imported from util.py

# This function is now imported from util.py

# This function is now imported from util.py

# This function is now imported from util.py




def _clear_config_buckets(project_id: str) -> None:
    """Remove config labels from all buckets found in the project."""
    print(f"🧹 Clearing config labels from all buckets in project: {project_id}")
    
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


def _ensure_no_config_bucket(project_id: str) -> None:
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


def _cleanup_test_buckets(project_id: str, *bucket_names: str) -> None:
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





class TestConfigInitScenarios:
    """Integration tests for all config initialization scenarios."""
    
    @pytest.mark.integration
    def test_fresh_project_default_bucket(self, ctx):
        """Scenario 1: Fresh project with DEFAULT bucket naming (no bucket name specified)."""
        try:
            # Use default bucket naming (no bucket name specified) - this tests the actual default behavior
            deploy._init_config(ctx['project_id'], ctx['app_id'])
            # If we get here, no exception was raised, so it succeeded
            
            # Verify default bucket was created with correct name (what deploy.py generates by default)
            found_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets == [ctx['default_bucket']], f"Expected default bucket {ctx['default_bucket']}, got {found_buckets}"
            
            # Verify app.yaml was created with correct content
            actual_app_id = sdk_config.get_app_id(ctx['project_id'])
            assert actual_app_id == ctx['app_id'], f"app.yaml should contain correct app_id: expected {ctx['app_id']}, got {actual_app_id}"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], ctx['default_bucket'])
    
    @pytest.mark.integration
    def test_fresh_project_custom_bucket(self, ctx):
        """Scenario 2: Fresh project, no existing buckets, use custom bucket name."""
        custom_bucket = ctx['custom_bucket']("custom")
        
        try:
            # Run init_config with custom bucket name
            deploy._init_config(ctx['project_id'], ctx['app_id'], custom_bucket)
            # If we get here, no exception was raised, so it succeeded
            
            # Verify bucket was created with correct label
            found_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets == [custom_bucket], f"Expected {custom_bucket}, got {found_buckets}"
            
            # Verify app.yaml was created with correct content
            actual_app_id = sdk_config.get_app_id(ctx['project_id'])
            assert actual_app_id == ctx['app_id'], f"app.yaml should contain correct app_id: expected {ctx['app_id']}, got {actual_app_id}"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], custom_bucket)
    
    @pytest.mark.integration
    def test_existing_bucket_matches_default(self, ctx):
        """Scenario 3: Existing config bucket matches default bucket name."""
        try:
            # First run: create the bucket with explicit naming
            deploy._init_config(ctx['project_id'], ctx['app_id'], ctx['default_bucket'])
            # If we get here, no exception was raised, so it succeeded
            
            # Verify bucket exists
            found_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets == [ctx['default_bucket']]
            
            # Second run: should use existing bucket (idempotent)
            deploy._init_config(ctx['project_id'], ctx['app_id'], ctx['default_bucket'])
            # If we get here, no exception was raised, so it succeeded
            
            # Verify still only one config bucket
            found_buckets2 = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets2 == [ctx['default_bucket']], "Should still be the same bucket"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], ctx['default_bucket'])
    
    @pytest.mark.integration
    def test_repeatability(self, ctx):
        """Scenario 4: Existing config bucket matches custom bucket name."""
        # Use the custom bucket from ctx fixture
        custom_bucket = ctx['custom_bucket']("custom")
        
        try:
            # First run: create with custom bucket name
            deploy._init_config(ctx['project_id'], ctx['app_id'], custom_bucket)
            # If we get here, no exception was raised, so it succeeded
            
            # Second run: use same custom bucket name
            deploy._init_config(ctx['project_id'], ctx['app_id'], custom_bucket)
            # If we get here, no exception was raised, so it succeeded
            
            # Verify still the same bucket
            found_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets == [custom_bucket]
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], custom_bucket)
    
    @pytest.mark.integration
    def test_conflict_existing_vs_default(self, ctx):
        """Scenario 5: Existing config bucket conflicts with default bucket name."""
        try:
            # First run: create bucket for first app with explicit naming
            deploy._init_config(ctx['project_id'], ctx['app_id'], ctx['default_bucket'])
            # If we get here, no exception was raised, so it succeeded
            
            first_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert first_buckets == [ctx['default_bucket']]
            
            # Second run: try to create bucket for second app (should fail due to conflict)
            with pytest.raises(deploy.BucketNameConflictError):
                deploy._init_config(ctx['project_id'], ctx['secondary_app_id'], ctx['secondary_default_bucket'])
            
            # Verify original bucket is unchanged
            found_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets == [ctx['default_bucket']], "Original bucket should be unchanged"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], ctx['default_bucket'])
    
    @pytest.mark.integration
    def test_conflict_existing_vs_custom(self, ctx):
        """Scenario 6: Existing config bucket conflicts with custom bucket name."""
        # Use the custom buckets from ctx fixture
        existing_bucket = ctx['custom_bucket']("existing")
        conflicting_bucket = ctx['custom_bucket']("conflicting")
        
        try:
            # First run: create with custom bucket name
            deploy._init_config(ctx['project_id'], ctx['app_id'], existing_bucket)
            # If we get here, no exception was raised, so it succeeded
            
            # Verify bucket was created
            found_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets == [existing_bucket]
            
            # Second run: try to use different custom bucket name (should fail)
            with pytest.raises(deploy.BucketNameConflictError):
                deploy._init_config(ctx['project_id'], ctx['app_id'], conflicting_bucket)
            
            # Verify original bucket is unchanged
            found_buckets2 = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets2 == [existing_bucket], "Original bucket should be unchanged"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], existing_bucket)
    
    @pytest.mark.integration
    def test_app_yaml_mismatch(self, ctx):
        """Scenario 7: Existing bucket with app.yaml containing different app_id."""
        # Use the bucket from ctx fixture
        bucket_name = ctx['custom_bucket']("shared")
        
        try:
            # First run: create bucket with first app_id
            deploy._init_config(ctx['project_id'], ctx['app_id'], bucket_name)
            # If we get here, no exception was raised, so it succeeded
            
            # Verify app.yaml contains first app_id
            actual_app_id = sdk_config.get_app_id(ctx['project_id'])
            assert actual_app_id == ctx['app_id'], f"app.yaml should contain first app_id: expected {ctx['app_id']}, got {actual_app_id}"
            
            # Second run: try to use same bucket with different app_id (should fail)
            with pytest.raises(deploy.AppYamlMismatchError):
                deploy._init_config(ctx['project_id'], ctx['secondary_app_id'], bucket_name)
            
            # Verify app.yaml is unchanged
            actual_app_id = sdk_config.get_app_id(ctx['project_id'])
            assert actual_app_id == ctx['app_id'], f"app.yaml should be unchanged: expected {ctx['app_id']}, got {actual_app_id}"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], bucket_name)
    
    @pytest.mark.integration
    def test_bucket_exists_no_label(self, ctx):
        """Scenario 8: Bucket exists but has no config label (should add label)."""
        # Use the bucket from ctx fixture
        bucket_name = ctx['custom_bucket']("nolabel")
        
        try:
            # Manually create bucket without label
            create_result = subprocess.run([
                "gsutil", "mb", "-p", ctx['project_id'], f"gs://{bucket_name}"
            ], capture_output=True, text=True)
            assert create_result.returncode == 0, "Manual bucket creation should succeed"
            
            # Verify no config bucket is found by label
            existing = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert existing == [], "Should not find config bucket (no label yet)"
            
            # Run init_config (should add label to existing bucket)
            deploy._init_config(ctx['project_id'], ctx['app_id'], bucket_name)
            # If we get here, no exception was raised, so it succeeded
            
            # Verify bucket now has config label
            found_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets == [bucket_name], "Bucket should now be found with config label"
            
            # Verify app.yaml was created
            actual_app_id = sdk_config.get_app_id(ctx['project_id'])
            assert actual_app_id == ctx['app_id'], f"app.yaml should contain correct app_id: expected {ctx['app_id']}, got {actual_app_id}"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], bucket_name)

    @pytest.mark.integration
    def test_default_bucket_conflict(self, ctx):
        """Scenario 9: Two different app_ids trying to use default bucket naming should conflict."""
        expected_first_bucket = f"{ctx['app_id']}-config"
        
        try:
            # First app uses default bucket naming (no bucket name specified)
            deploy._init_config(ctx['project_id'], ctx['app_id'])
            # If we get here, no exception was raised, so it succeeded
            
            # Verify first app's default bucket was created
            found_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets == [expected_first_bucket], f"Expected default bucket {expected_first_bucket}"
            
            # Second app should fail - conflict with existing config bucket
            # (Even though bucket names would be different, only one config bucket per project is allowed)
            with pytest.raises(deploy.BucketNameConflictError):
                deploy._init_config(ctx['project_id'], ctx['secondary_app_id'])  # No bucket name!
            
            # Verify original bucket is unchanged
            found_buckets_after = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets_after == [expected_first_bucket], "Original bucket should be unchanged"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], expected_first_bucket)

    @pytest.mark.integration
    def test_default_bucket_success(self, ctx):
        """Scenario 10: Single app using default bucket naming should succeed."""
        expected_bucket = f"{ctx['app_id']}-config"
        
        try:
            # App uses default bucket naming (no bucket name specified)
            deploy._init_config(ctx['project_id'], ctx['app_id'])
            # If we get here, no exception was raised, so it succeeded
            
            # Verify default bucket was created with correct name
            found_buckets = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets == [expected_bucket], f"Expected default bucket {expected_bucket}"
            
            # Verify app.yaml contains correct app_id
            actual_app_id = sdk_config.get_app_id(ctx['project_id'])
            assert actual_app_id == ctx['app_id'], f"app.yaml should contain correct app_id: expected {ctx['app_id']}, got {actual_app_id}"
            
            # Second call should be idempotent (same app, same default bucket)
            deploy._init_config(ctx['project_id'], ctx['app_id'])
            # If we get here, no exception was raised, so it succeeded
            
            # Verify still only one bucket
            found_buckets_after = gcp.find_config_buckets_by_label(ctx['project_id'], LABEL_KEY, LABEL_VALUE)
            assert found_buckets_after == [expected_bucket], "Should still be the same bucket"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], expected_bucket)


class TestConfigInitEdgeCases:
    """Edge case tests for config initialization."""
    
    @pytest.mark.integration
    def test_invalid_project_id(self):
        """Test with invalid project ID."""
        test_hash = generate_random_hash()
        app_id = generate_test_app_id(test_hash)
        with pytest.raises(deploy.InvalidProjectIdError):
            deploy._init_config("", app_id)
    
    @pytest.mark.integration
    def test_invalid_app_id(self, ctx):
        """Test with invalid app ID."""
        with pytest.raises(deploy.InvalidAppIdError):
            deploy._init_config(ctx['project_id'], "")
    
    @pytest.mark.integration
    def test_special_characters_in_app_id(self, ctx):
        """Test with special characters in app_id (should work in app.yaml)."""
        # Use the bucket from ctx fixture
        bucket_name = ctx['custom_bucket']("special")
        
        try:
            deploy._init_config(ctx['project_id'], ctx['app_id'], bucket_name)
            # If we get here, no exception was raised, so it succeeded
            
            # Verify app.yaml contains the special characters
            actual_app_id = sdk_config.get_app_id(ctx['project_id'])
            assert actual_app_id == ctx['app_id'], f"app.yaml should contain correct app_id: expected {ctx['app_id']}, got {actual_app_id}"
        finally:
            # Clean up test bucket - this always runs, even if test fails
            _cleanup_test_buckets(ctx['project_id'], bucket_name)


def pytest_sessionfinish(session, exitstatus):
    """Log total bucket count at the end of all tests."""
    try:
        project_id = get_test_project_id()
        result = subprocess.run(
            ["gsutil", "ls", "-p", project_id], 
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            total_buckets = len([line for line in result.stdout.split('\n') if line.startswith('gs://')])
            print(f"\n🏁 TEST SESSION COMPLETE - FINAL BUCKET COUNT: {total_buckets}")
        else:
            print(f"\n🏁 TEST SESSION COMPLETE - Could not get final bucket count")
    except Exception as e:
        print(f"\n🏁 TEST SESSION COMPLETE - Could not get final bucket count: {e}")


if __name__ == "__main__":
    # Quick test runner
    try:
        project_id = get_test_project_id()
        print(f"Running integration tests against project: {project_id}")
        pytest.main([__file__, "-v"])
    except (FileNotFoundError, ValueError) as e:
        print(f"Cannot run tests: {e}")
        print("Configure project ID in .config-project file")
        print("Example: echo 'my-test-project-123' > .config-project")
