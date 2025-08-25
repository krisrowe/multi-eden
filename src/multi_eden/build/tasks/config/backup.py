"""
Configuration backup functionality.

This module handles backing up local configuration files to GCS buckets
using Terraform for infrastructure management.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional
from invoke import task


@task
def config_env_backup(
    ctx,
    env: str = None,
    config_dir: str = None,
    project_id: str = None,
    force: bool = False,
    all: bool = False
) -> bool:
    """
    Backup local configuration to GCS bucket using Terraform.
    
    Args:
        env: Environment name to backup (e.g., 'dev', 'prod', 'test'). Required unless --all is specified.
        config_dir: Path to local config directory (defaults to repo_root/config/)
        project_id: GCP Project ID (defaults to reading from .config-project)
        force: Force backup even if no changes detected
        all: Backup all environments instead of a specific one
        
    Returns:
        True if backup was successful, False otherwise
        
    Raises:
        RuntimeError: If backup fails or required files are missing
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
        
        # Validate config directory exists
        if not Path(config_dir).exists():
            raise RuntimeError(f"Local config directory not found: {config_dir}")
        
        # Determine project ID from .config-project file
        if project_id is None:
            try:
                from .util import get_project_id_from_config
            except ImportError:
                from util import get_project_id_from_config
            project_id = get_project_id_from_config(cwd)
        
        if all:
            print(f"🔧 Backing up ALL environments to GCS bucket...")
        else:
            print(f"🔧 Backing up configuration for environment '{env}' to GCS bucket...")
        print(f"📁 Source: {config_dir}")
        print(f"🏗️  Project: {project_id}")
        
        # Find the config bucket using shared utility
        try:
            from .util import find_config_bucket
        except ImportError:
            from util import find_config_bucket
        
        config_bucket = find_config_bucket(project_id)
        print(f"🎯 Found config bucket: {config_bucket}")
        
        # Use gsutil rsync directly instead of terraform
        print(f"🔄 Starting smart sync to GCS bucket...")
        
        try:
            # Use gsutil rsync for smart timestamp-based syncing
            sync_result = subprocess.run([
                "gsutil", "-m", "rsync", "-r", config_dir, config_bucket
            ], capture_output=True, text=True, timeout=300)
            
            if sync_result.returncode != 0:
                raise RuntimeError(f"gsutil rsync failed: {sync_result.stderr}")
            
            if all:
                print(f"✅ All environments backup complete!")
            else:
                print(f"✅ Configuration backup complete for '{env}'!")
            print(f"💡 Configuration backed up to: {config_bucket}")
            return True
            
        except Exception as e:
            print(f"❌ Configuration backup failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Configuration backup failed: {e}")
        return False


def main():
    """CLI entry point for backup-config command."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Backup local configuration to GCS")
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
        help="Force backup even if no changes detected"
    )
    
    args = parser.parse_args()
    
    success = config_env_backup(
        config_dir=args.config_dir,
        project_id=args.project_id,
        force=args.force
    )
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
