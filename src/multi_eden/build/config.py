"""
Configuration utilities for the build package.
"""

from typing import Dict, Any
from pathlib import Path


def get_tasks_config() -> Dict[str, Any]:
    """
    Get tasks configuration.
    
    Returns:
        Dict containing tasks configuration
    """
    # For now, return a basic configuration
    # This can be expanded later to read from actual config files
    return {
        'tasks': {
            'test': {
                'env': 'unit-testing',
                'description': 'Run tests for a specific suite'
            },
            'build': {
                'env': 'production',
                'description': 'Build Docker image'
            },
            'deploy': {
                'env': 'production', 
                'description': 'Deploy to cloud'
            }
        }
    }


def get_build_config() -> Dict[str, Any]:
    """
    Get build configuration.
    
    Returns:
        Dict containing build configuration
    """
    # This can be expanded to read from actual config files
    return {
        'project_id': 'multi-eden',
        'image_name': 'multi-eden-api'
    }
