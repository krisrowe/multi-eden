#!/usr/bin/env python3
"""
Centralized logging configuration.

This module provides a bootstrap_logging function that can be imported from any entry point
to configure logging consistently across the application.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import yaml


def _load_logging_config() -> Dict[str, Any]:
    """
    Load logging configuration from config.yaml.
    
    Returns:
        Dictionary containing logging configuration with defaults applied.
    """
    # Default logging configuration
    default_config = {
        'logging': {
            'enabled': True,
            'level': 'INFO',
            'format': '%(levelname)s: %(name)s: %(message)s',
            'handlers': {
                'console': {
                    'enabled': True,
                    'level': 'INFO'
                },
                'file': {
                    'enabled': False,
                    'level': 'DEBUG',
                    'filename': 'app.log',
                    'max_bytes': 10485760,  # 10MB
                    'backup_count': 5
                }
            }
        }
    }
    
    # Check for LOG_LEVEL environment variable first (takes precedence)
    env_log_level = os.environ.get('LOG_LEVEL')
    if env_log_level and env_log_level.strip():
        # Environment variable takes precedence
        env_level = env_log_level.strip().upper()
        if env_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            print(f"LOG_LEVEL environment variable set to: {env_level}", file=sys.stderr)
            # Override the level in our config
            default_config['logging']['level'] = env_level
            # Also override console handler level to match
            default_config['logging']['handlers']['console']['level'] = env_level
    
    try:
        # Try to load from config.yaml
        config_path = Path(__file__).parent / 'config.yaml'
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                if config and 'logging' in config:
                    # Merge with defaults
                    logging_config = default_config['logging'].copy()
                    logging_config.update(config['logging'])
                    return logging_config
    except Exception as e:
        # If anything goes wrong, log a warning and use defaults
        print(f"Warning: Failed to load logging config from config.yaml: {e}", file=sys.stderr)
        print("Using default logging configuration", file=sys.stderr)
    
    return default_config['logging']


def bootstrap_logging(name: Optional[str] = None) -> None:
    """
    Bootstrap logging configuration for the application.
    
    This function:
    1. Loads logging configuration from config.yaml
    2. Sets up handlers (console, file) based on configuration
    3. Configures the root logger with the specified level and format
    4. Can be called from any entry point to ensure consistent logging
    
    Args:
        name: Optional name for the logger (defaults to root logger)
    """
    config = _load_logging_config()
    
    if not config.get('enabled', True):
        # Logging disabled - set root logger to CRITICAL to suppress all output
        logging.getLogger().setLevel(logging.CRITICAL)
        return
    
    # Parse log level
    level_name = config.get('level', 'INFO').upper()
    try:
        level = getattr(logging, level_name)
    except AttributeError:
        print(f"Warning: Invalid log level '{level_name}', using INFO", file=sys.stderr)
        level = logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(config.get('format', '%(levelname)s: %(name)s: %(message)s'))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    if config.get('handlers', {}).get('console', {}).get('enabled', True):
        console_handler = logging.StreamHandler(sys.stderr)
        console_level = config.get('handlers', {}).get('console', {}).get('level', 'INFO')
        try:
            console_handler.setLevel(getattr(logging, console_level.upper()))
        except AttributeError:
            console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler
    file_config = config.get('handlers', {}).get('file', {})
    if file_config.get('enabled', False):
        try:
            filename = file_config.get('filename', 'app.log')
            max_bytes = file_config.get('max_bytes', 10485760)
            backup_count = file_config.get('backup_count', 5)
            
            file_handler = logging.handlers.RotatingFileHandler(
                filename, maxBytes=max_bytes, backupCount=backup_count
            )
            file_level = file_config.get('level', 'DEBUG')
            try:
                file_handler.setLevel(getattr(logging, file_level.upper()))
            except AttributeError:
                file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Failed to set up file logging: {e}", file=sys.stderr)
    
    # If no handlers were added, add a basic console handler
    if not root_logger.handlers:
        basic_handler = logging.StreamHandler(sys.stdout)
        basic_handler.setLevel(level)
        basic_handler.setFormatter(formatter)
        root_logger.addHandler(basic_handler)
    
    # Log that logging has been configured
    if name:
        logger = logging.getLogger(name)
        logger.debug(f"Logging configured for {name}")
    else:
        logging.debug("Logging configured for root logger")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name, ensuring logging is bootstrapped.
    
    Args:
        name: Name for the logger
        
    Returns:
        Configured logger instance
    """
    # Ensure logging is bootstrapped
    bootstrap_logging()
    return logging.getLogger(name)


def bootstrap_logging_on_import(module_name: str = None):
    """
    Decorator that automatically bootstraps logging when a module is imported.
    
    Usage:
        @bootstrap_logging_on_import()
        class SomeClass:
            pass
            
        # Or with a specific module name:
        @bootstrap_logging_on_import("my_module")
        def some_function():
            pass
    """
    def decorator(obj):
        # Bootstrap logging when the decorator is applied
        if module_name:
            bootstrap_logging(module_name)
        else:
            # Try to get the module name from the decorated object
            try:
                if hasattr(obj, '__module__'):
                    bootstrap_logging(obj.__module__)
                else:
                    bootstrap_logging()
            except:
                bootstrap_logging()
        return obj
    return decorator


def auto_bootstrap_logging():
    """
    Decorator that automatically bootstraps logging for the entire module.
    
    Usage:
        # At the top of any module file:
        from multi_eden.run.config.logging import auto_bootstrap_logging
        
        @auto_bootstrap_logging()
        class SomeClass:
            pass
            
        # Or just call it directly:
        auto_bootstrap_logging()(None)  # This will bootstrap logging immediately
    """
    def decorator(obj):
        # Bootstrap logging immediately
        bootstrap_logging()
        return obj
    return decorator


# Example usage at module level:
# from config.logging import auto_bootstrap_logging
# auto_bootstrap_logging()(None)  # Bootstrap logging when module is imported
