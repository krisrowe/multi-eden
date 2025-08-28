"""
Shared utilities for configuration management tasks.
"""

from pathlib import Path
from typing import Optional
from .constants import CONFIG_BUCKET_LABEL_KEY, CONFIG_BUCKET_LABEL_VALUE


def find_config_bucket(project_id: str) -> str:
    """
    Find the configuration bucket for a project using the standard label.
    
    Args:
        project_id: GCP Project ID to search in
        
    Returns:
        The GCS bucket name (without gs:// prefix)
        
    Raises:
        RuntimeError: If no bucket found or multiple buckets found
    """
    from multi_eden.internal import gcp
    
    existing_config_buckets = gcp.find_config_buckets_by_label(
        project_id, CONFIG_BUCKET_LABEL_KEY, CONFIG_BUCKET_LABEL_VALUE
    )
    
    if not existing_config_buckets:
        raise RuntimeError(
            f"Cannot identify config bucket in project '{project_id}' with label "
            f"'{CONFIG_BUCKET_LABEL_KEY}:{CONFIG_BUCKET_LABEL_VALUE}'. "
            f"If this is the first time setting up configuration, run 'invoke init-config'. "
            f"If not, the project ID in .config-project may be incorrect."
        )
    
    if len(existing_config_buckets) > 1:
        raise RuntimeError(
            f"Multiple config buckets found in project '{project_id}': {existing_config_buckets}. "
            f"This indicates a configuration issue. Please contact your administrator."
        )
    
    return f"gs://{existing_config_buckets[0]}"


def get_project_id_from_config(repo_root: Path = None) -> str:
    """
    Get project ID from .config-project file.
    
    Args:
        repo_root: Repository root path (defaults to current working directory)
        
    Returns:
        The project ID from .config-project file
        
    Raises:
        RuntimeError: If .config-project file not found or empty
    """
    if repo_root is None:
        # Use current working directory (where user ran the command)
        repo_root = Path.cwd()
    
    project_id_file = repo_root / ".config-project"
    if not project_id_file.exists():
        raise RuntimeError(".config-project file not found. Run 'invoke init-config' first to set up configuration.")
    
    project_id = project_id_file.read_text().strip()
    if not project_id:
        raise RuntimeError("Project ID is empty in .config-project file. Run 'invoke init-config' first.")
    
    return project_id


def get_repo_root() -> Path:
    """Get the current working directory (project root where user runs tasks)."""
    # For pip-installed library, use current working directory
    # Users will run tasks from their project root
    return Path.cwd()


def get_config_dir(config_dir: Optional[str] = None) -> str:
    """
    Get the config directory path, defaulting to repo_root/config if not specified.
    
    Args:
        config_dir: Optional custom config directory path
        
    Returns:
        Resolved config directory path as string
    """
    repo_root = get_repo_root()
    
    if config_dir is None:
        config_dir = str(repo_root / "config")
    else:
        config_dir = str(Path(config_dir).resolve())
    
    return config_dir