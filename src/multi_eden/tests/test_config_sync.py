"""
Tests for config sync operations (backup-config and restore-config).
Tests backup and restore functionality using ephemeral directories.
"""

import os
import pytest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from .util import (
    create_test_context,
    ensure_clean_project_state,
    cleanup_test_buckets,
    create_ephemeral_config_dir,
    create_dummy_config_files,
    verify_config_files_in_bucket,
    verify_config_files_in_local_dir
)


class TestConfigSync:
    """Test config sync operations (backup and restore)."""
    
    def _setup_test_environment(self, env: str = "test"):
        """
        Private helper method for setting up test environment.
        Initializes config project and creates ephemeral local folder.
        """
        # Create test context
        ctx = create_test_context()
        project_id = ctx['project_id']
        app_id = ctx['app_id']
        bucket_name = ctx['default_bucket']
        
        # Ensure clean project state
        ensure_clean_project_state(project_id)
        
        # Initialize config bucket
        print(f"🚀 Initializing config bucket: {bucket_name}")
        from ..config import deploy
        deploy._init_config(project_id, app_id, bucket_name)
        
        # Verify bucket was created
        from ..internal import gcp
        found_buckets = gcp.find_config_buckets_by_label(project_id, "multi-env-sdk", "config")
        assert bucket_name in found_buckets, f"Config bucket {bucket_name} should exist"
        
        # Create ephemeral config directory
        config_dir = create_ephemeral_config_dir()
        
        # Create dummy config files
        create_dummy_config_files(config_dir, env)
        
        # Verify local files exist
        assert verify_config_files_in_local_dir(config_dir, env), "Local config files should exist"
        
        return {
            'ctx': ctx,
            'project_id': project_id,
            'app_id': app_id,
            'bucket_name': bucket_name,
            'config_dir': config_dir,
            'env': env
        }
    
    @pytest.mark.integration
    def test_backup_config(self):
        """Test backup-config functionality."""
        test_env = "test-backup"
        test_data = self._setup_test_environment(test_env)
        
        try:
            # Run backup-config command
            print(f"📤 Running backup-config for environment: {test_env}")
            
            # Temporarily change working directory to config directory
            original_cwd = os.getcwd()
            os.chdir(test_data['config_dir'].parent)
            
            try:
                # Run backup-config with the ephemeral config directory
                result = subprocess.run([
                    "python3", "-m", "multi_env_sdk.tasks", "backup-config",
                    "--config-dir", str(test_data['config_dir']),
                    "--env", test_env,
                    "--config-env", "static"
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode != 0:
                    print(f"❌ backup-config failed: {result.stderr}")
                    pytest.fail(f"backup-config command failed: {result.stderr}")
                
                print(f"✅ backup-config completed successfully")
                print(f"📤 Output: {result.stdout}")
                
                # Verify files were uploaded to the bucket
                assert verify_config_files_in_bucket(
                    test_data['bucket_name'], 
                    test_env
                ), "Config files should exist in bucket after backup"
                
                print(f"✅ Backup verification successful")
                
            finally:
                # Restore original working directory
                os.chdir(original_cwd)
                
        finally:
            # Clean up test bucket
            cleanup_test_buckets(test_data['project_id'], test_data['bucket_name'])
    
    @pytest.mark.integration
    def test_restore_config(self):
        """Test restore-config functionality."""
        test_env = "test-restore"
        test_data = self._setup_test_environment(test_env)
        
        try:
            # First, backup some config files
            print(f"📤 Running initial backup for restore test")
            
            # Temporarily change working directory to config directory
            original_cwd = os.getcwd()
            os.chdir(test_data['config_dir'].parent)
            
            try:
                # Run backup-config
                backup_result = subprocess.run([
                    "python3", "-m", "multi_env_sdk.tasks", "backup-config",
                    "--config-dir", str(test_data['config_dir']),
                    "--env", test_env,
                    "--config-env", "static"
                ], capture_output=True, text=True, timeout=60)
                
                if backup_result.returncode != 0:
                    pytest.fail(f"Initial backup failed: {backup_result.stderr}")
                
                print(f"✅ Initial backup completed")
                
                # Verify files are in bucket
                assert verify_config_files_in_bucket(
                    test_data['bucket_name'], 
                    test_env
                ), "Config files should exist in bucket after backup"
                
                # Now test restore by creating a new ephemeral directory
                restore_config_dir = create_ephemeral_config_dir()
                
                try:
                    # Run restore-config command
                    print(f"📥 Running restore-config for environment: {test_env}")
                    
                    restore_result = subprocess.run([
                        "python3", "-m", "multi_env_sdk.tasks", "restore-config",
                        "--config-dir", str(restore_config_dir),
                        "--env", test_env,
                        "--config-env", "static"
                    ], capture_output=True, text=True, timeout=60)
                    
                    if restore_result.returncode != 0:
                        print(f"❌ restore-config failed: {restore_result.stderr}")
                        pytest.fail(f"restore-config command failed: {restore_result.stderr}")
                    
                    print(f"✅ restore-config completed successfully")
                    print(f"📥 Output: {restore_result.stdout}")
                    
                    # Verify files were restored to local directory
                    assert verify_config_files_in_local_dir(
                        restore_config_dir, 
                        test_env
                    ), "Config files should exist in local directory after restore"
                    
                    print(f"✅ Restore verification successful")
                    
                finally:
                    # Clean up restore config directory
                    import shutil
                    shutil.rmtree(restore_config_dir.parent, ignore_errors=True)
                
            finally:
                # Restore original working directory
                os.chdir(original_cwd)
                
        finally:
            # Clean up test bucket
            cleanup_test_buckets(test_data['project_id'], test_data['bucket_name'])
    
    @pytest.mark.integration
    def test_backup_restore_cycle(self):
        """Test complete backup-restore cycle with verification."""
        test_env = "test-cycle"
        test_data = self._setup_test_environment(test_env)
        
        try:
            # Step 1: Backup config files
            print(f"🔄 Step 1: Running backup-config")
            
            original_cwd = os.getcwd()
            os.chdir(test_data['config_dir'].parent)
            
            try:
                backup_result = subprocess.run([
                    "python3", "-m", "multi_env_sdk.tasks", "backup-config",
                    "--config-dir", str(test_data['config_dir']),
                    "--env", test_env,
                    "--config-env", "static"
                ], capture_output=True, text=True, timeout=60)
                
                if backup_result.returncode != 0:
                    pytest.fail(f"Backup failed: {backup_result.stderr}")
                
                print(f"✅ Backup completed")
                
                # Step 2: Verify files in bucket
                assert verify_config_files_in_bucket(
                    test_data['bucket_name'], 
                    test_env
                ), "Files should exist in bucket after backup"
                
                print(f"✅ Bucket verification passed")
                
                # Step 3: Create new ephemeral directory for restore
                restore_config_dir = create_ephemeral_config_dir()
                
                try:
                    # Step 4: Restore config files
                    print(f"🔄 Step 4: Running restore-config")
                    
                    restore_result = subprocess.run([
                        "python3", "-m", "multi_env_sdk.tasks", "restore-config",
                        "--config-dir", str(restore_config_dir),
                        "--env", test_env,
                        "--config-env", "static"
                    ], capture_output=True, text=True, timeout=60)
                    
                    if restore_result.returncode != 0:
                        pytest.fail(f"Restore failed: {restore_result.stderr}")
                    
                    print(f"✅ Restore completed")
                    
                    # Step 5: Verify restored files
                    assert verify_config_files_in_local_dir(
                        restore_config_dir, 
                        test_env
                    ), "Files should exist in local directory after restore"
                    
                    print(f"✅ Local verification passed")
                    
                    # Step 6: Compare file contents (basic check)
                    original_secrets = test_data['config_dir'] / "secrets.json"
                    restored_secrets = restore_config_dir / "secrets.json"
                    
                    if original_secrets.exists() and restored_secrets.exists():
                        original_content = original_secrets.read_text()
                        restored_content = restored_secrets.read_text()
                        
                        # Basic content verification (should contain same env)
                        assert test_env in restored_content, "Restored file should contain environment name"
                        print(f"✅ Content verification passed")
                    else:
                        pytest.fail("Could not compare file contents")
                    
                    print(f"🔄 Complete backup-restore cycle successful!")
                    
                finally:
                    # Clean up restore config directory
                    import shutil
                    shutil.rmtree(restore_config_dir.parent, ignore_errors=True)
                
            finally:
                # Restore original working directory
                os.chdir(original_cwd)
                
        finally:
            # Clean up test bucket
            cleanup_test_buckets(test_data['project_id'], test_data['bucket_name'])


def pytest_sessionfinish(session, exitstatus):
    """Log total bucket count at the end of all tests."""
    try:
        from .util import get_test_project_id
        project_id = get_test_project_id()
        result = subprocess.run([
            "gsutil", "ls", "-p", project_id], 
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
        from .util import get_test_project_id
        project_id = get_test_project_id()
        print(f"Running config sync tests against project: {project_id}")
        pytest.main([__file__, "-v"])
    except Exception as e:
        print(f"Cannot run tests: {e}")
        print("Configure project ID in .config-project file")
        print("Example: echo 'my-test-project-123' > .config-project")
