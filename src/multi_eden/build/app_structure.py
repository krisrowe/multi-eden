"""
App Structure Detection and Validation

Automatically detects the main application module and validates
the repository structure for Multi-Eden SDK compatibility.
"""

import os
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class AppStructureError(Exception):
    """Raised when app structure is invalid or incompatible."""
    pass


def detect_main_module(base_path: str = ".") -> str:
    """
    Auto-detect the main application module.
    
    Looks for directories containing __main__.py that follow the pattern
    of being the primary application module.
    
    Args:
        base_path: Path to search in (defaults to current directory)
        
    Returns:
        Name of the main module directory
        
    Raises:
        AppStructureError: If no main module found or multiple candidates
    """
    base_path = Path(base_path)
    
    # Find all directories with __main__.py
    main_modules = []
    for item in base_path.iterdir():
        if (item.is_dir() and 
            not item.name.startswith('.') and 
            not item.name.startswith('_') and
            item.name not in ['tests', 'docs', 'scripts', 'venv', 'env'] and
            (item / '__main__.py').exists()):
            main_modules.append(item.name)
    
    if len(main_modules) == 0:
        raise AppStructureError(
            "No main module found. Expected a directory with __main__.py that contains "
            "serve/CLI routing logic. See Multi-Eden SDK documentation for required structure."
        )
    elif len(main_modules) == 1:
        logger.info(f"Auto-detected main module: {main_modules[0]}")
        return main_modules[0]
    else:
        raise AppStructureError(
            f"Multiple main modules found: {main_modules}. "
            "Multi-Eden apps should have exactly one main module directory. "
            "Consider consolidating or excluding non-main modules from the build."
        )


def validate_main_module_structure(module_name: str, base_path: str = ".") -> Dict[str, Any]:
    """
    Validate that the main module has the required structure.
    
    Args:
        module_name: Name of the main module directory
        base_path: Base path to search in
        
    Returns:
        Dict with validation results and metadata
        
    Raises:
        AppStructureError: If structure is invalid
    """
    module_path = Path(base_path) / module_name
    main_file = module_path / '__main__.py'
    
    if not main_file.exists():
        raise AppStructureError(f"Missing {main_file} - required for Multi-Eden apps")
    
    # Check if __main__.py has serve routing
    try:
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        has_serve_routing = (
            'serve' in content and 
            'sys.argv' in content and
            ('api' in content or 'server' in content)
        )
        
        if not has_serve_routing:
            logger.warning(
                f"{main_file} may not have proper serve/CLI routing. "
                "Expected pattern: if sys.argv[1] == 'serve': start_api_server()"
            )
            
    except Exception as e:
        logger.warning(f"Could not analyze {main_file}: {e}")
        has_serve_routing = False
    
    return {
        'module_name': module_name,
        'module_path': str(module_path),
        'has_serve_routing': has_serve_routing,
        'main_file': str(main_file)
    }


def validate_app_structure(base_path: str = ".") -> Dict[str, Any]:
    """
    Comprehensive validation of app structure for Multi-Eden compatibility.
    
    Args:
        base_path: Path to validate
        
    Returns:
        Dict with validation results and recommendations
        
    Raises:
        AppStructureError: If structure is incompatible
    """
    base_path = Path(base_path)
    
    # Check for requirements.txt
    requirements_file = base_path / 'requirements.txt'
    if not requirements_file.exists():
        raise AppStructureError(
            "Missing requirements.txt - required for Docker builds. "
            "Create this file with your production dependencies."
        )
    
    # Detect and validate main module
    main_module = detect_main_module(base_path)
    module_info = validate_main_module_structure(main_module, base_path)
    
    # Check for sensitive files that shouldn't be in Docker
    sensitive_patterns = [
        '.env', '.env.*', 'secrets.*', '*.key', '*.pem', 
        '.config-project', 'config/env/', 'config/secrets/'
    ]
    
    sensitive_files = []
    for pattern in sensitive_patterns:
        sensitive_files.extend(base_path.glob(pattern))
    
    # Check for development files
    dev_files = []
    dev_patterns = ['venv/', '.venv/', 'tests/', 'docs/', '__pycache__/']
    for pattern in dev_patterns:
        dev_files.extend(base_path.glob(pattern))
    
    return {
        'main_module': module_info,
        'requirements_file': str(requirements_file),
        'sensitive_files': [str(f) for f in sensitive_files],
        'dev_files': [str(f) for f in dev_files],
        'structure_valid': True,
        'recommendations': _generate_recommendations(module_info, sensitive_files, dev_files)
    }


def _generate_recommendations(module_info: Dict[str, Any], 
                            sensitive_files: List[Path], 
                            dev_files: List[Path]) -> List[str]:
    """Generate recommendations for improving app structure."""
    recommendations = []
    
    if not module_info.get('has_serve_routing'):
        recommendations.append(
            f"Add serve routing to {module_info['main_file']}. "
            "See Multi-Eden SDK documentation for the required pattern."
        )
    
    if sensitive_files:
        recommendations.append(
            f"Found {len(sensitive_files)} sensitive files that will be excluded from Docker. "
            "Ensure secrets are properly configured via environment variables."
        )
    
    if len(dev_files) > 10:
        recommendations.append(
            "Consider cleaning up development files to reduce Docker build context size."
        )
    
    return recommendations


def generate_dockerfile_content(module_name: str) -> str:
    """
    Generate Dockerfile content for the app using the SDK template.
    
    Args:
        module_name: Name of the main module
        
    Returns:
        Dockerfile content as string
    """
    template_path = Path(__file__).parent / 'config' / 'Dockerfile.template'
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Replace template variables
    dockerfile_content = template_content.replace('{{APP_MODULE}}', module_name)
    
    logger.debug(f"Generated Dockerfile content for module '{module_name}'")
    return dockerfile_content


def generate_dockerignore_content() -> str:
    """
    Generate .dockerignore content using the SDK template.
    
    Returns:
        .dockerignore content as string
    """
    template_path = Path(__file__).parent / 'config' / 'dockerignore.template'
    
    with open(template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    logger.debug("Generated .dockerignore content")
    return template_content


def create_dockerignore_if_missing(output_path: str = ".dockerignore") -> bool:
    """
    Create .dockerignore file only if it doesn't exist.
    
    Args:
        output_path: Where to write the .dockerignore file
        
    Returns:
        True if file was created, False if it already existed
    """
    if os.path.exists(output_path):
        return False
    
    content = generate_dockerignore_content()
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    logger.info(f"Created .dockerignore at {output_path}")
    return True
