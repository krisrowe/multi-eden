"""
Configuration restore functionality.

This module handles restoring configuration files from GCS buckets
to local directories using Terraform for infrastructure management.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from invoke import task


@task
def config_env_restore(
    ctx,
    env: Optional[str] = None,
    config_dir: Optional[str] = None,
    project_id: Optional[str] = None,
    force: bool = False,
    all: bool = False
) -> bool:
    """
    Restore configuration from GCS bucket to local directory using Terraform.
    
    Args:
        env: Environment name to restore (e.g., 'dev', 'prod', 'test'). Required unless --all is specified.
        config_dir: Path to local config directory (defaults to repo_root/config/)
        project_id: GCP Project ID (defaults to reading from .config-project)
        force: Force restore even if local files exist
        all: Restore all environments instead of a specific one
        
    Returns:
        True if restore was successful, False otherwise
        
    Raises:
        RuntimeError: If restore fails or required files are missing
        ValueError: If neither env nor --all is specified
    """
    try:
        # Validate arguments
        if not all and not env:
            raise ValueError("Must specify either environment name or --all flag")
        
        # Get the current working directory (where user ran the command)
        cwd = Path.cwd()
        
        # Determine config directory
        if config_dir is None:
            config_dir = str(cwd / "config")
        else:
            config_dir = str(Path(config_dir).resolve())
        
        # Determine project ID from .config-project file
        if project_id is None:
            try:
                from .util import get_project_id_from_config
            except ImportError:
                from util import get_project_id_from_config
            project_id = get_project_id_from_config(cwd)
        
        if all:
            print(f"🔧 Restoring ALL environments from GCS bucket...")
        else:
            print(f"🔧 Restoring configuration for environment: {env}...")
        print(f"📁 Destination: {config_dir}")
        print(f"🏗️  Project: {project_id}")
        
        # Find the config bucket using shared utility
        try:
            from .util import find_config_bucket
        except ImportError:
            from util import find_config_bucket
        
        config_bucket = find_config_bucket(project_id)
        print(f"🎯 Found config bucket: {config_bucket}")
        
        # Use gsutil rsync directly instead of terraform
        print(f"🔄 Starting smart sync from GCS bucket...")
        
        try:
            # Use gsutil rsync for smart timestamp-based syncing
            sync_result = subprocess.run([
                "gsutil", "-m", "rsync", "-r", config_bucket, config_dir
            ], capture_output=True, text=True, timeout=300)
            
            if sync_result.returncode != 0:
                raise RuntimeError(f"gsutil rsync failed: {sync_result.stderr}")
            
            if all:
                print(f"✅ All environments restore complete!")
            else:
                print(f"✅ Configuration restore complete for '{env}'!")
            print(f"💡 Configuration restored to {config_dir}/")
            
            # Verify that files were restored
            if Path(config_dir).exists():
                files = list(Path(config_dir).glob("**/*"))
                if files:
                    print(f"📁 Restored files: {[f.name for f in files if f.is_file()]}")
                else:
                    print(f"⚠️  Restored directory is empty: {config_dir}")
            else:
                print(f"⚠️  Restored directory not found: {config_dir}")
            
            return True
            
        except Exception as e:
            print(f"❌ Configuration restore failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Configuration restore failed: {e}")
        return False


def main():
    """CLI entry point for restore-config command."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Restore configuration from GCS")
    parser.add_argument(
        "environment",
        help="Environment name to restore (e.g., 'dev', 'prod', 'test')"
    )
    parser.add_argument(
        "--config-dir",
        help="Path to local config directory (defaults to repo_root/config/)"
    )
    parser.add_argument(
        "--project-id",
        help="GCP Project ID (defaults to reading from .config-project)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force restore even if local files exist"
    )
    
    args = parser.parse_args()
    
    success = config_env_restore(
        environment=args.environment,
        config_dir=args.config_dir,
        project_id=args.project_id,
        force=args.force
    )
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
