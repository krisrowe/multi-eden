#!/usr/bin/env python3
"""
Centralized logging configuration.

This module provides a bootstrap_logging function that can be imported from any entry point
to configure logging consistently across the application using Python's native INI format.
"""

import logging
import logging.config
import os
import sys
from pathlib import Path
from typing import Optional


def _find_logging_config() -> Optional[Path]:
    """
    Find the logging configuration file.
    
    Looks for logging.ini in the current working directory or core/ subdirectory.
    
    Returns:
        Path to logging configuration file, or None if not found.
    """
    # Check current directory first
    current_dir_config = Path('logging.ini')
    if current_dir_config.exists():
        return current_dir_config
    
    # Check core/ subdirectory
    core_dir_config = Path('core/logging.ini')
    if core_dir_config.exists():
        return core_dir_config
    
    # Check if we're in a subdirectory and look up
    parent_core_config = Path('../core/logging.ini')
    if parent_core_config.exists():
        return parent_core_config
    
    return None


def _setup_environment_variables():
    """
    Set up environment variables for logging configuration.
    
    Sets LOG_LEVEL to INFO if not already set, ensuring the INI file has a valid value.
    """
    if 'LOG_LEVEL' not in os.environ:
        os.environ['LOG_LEVEL'] = 'INFO'
    
    # Validate LOG_LEVEL
    log_level = os.environ['LOG_LEVEL'].strip().upper()
    if log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
        print(f"Warning: Invalid LOG_LEVEL '{log_level}', using INFO", file=sys.stderr)
        os.environ['LOG_LEVEL'] = 'INFO'


def bootstrap_logging(name: Optional[str] = None) -> None:
    """
    Bootstrap logging configuration for the application using Python's native INI format.
    
    This function:
    1. Sets up environment variables for INI file substitution
    2. Loads logging configuration from logging.ini using logging.config.fileConfig()
    3. Applies LOG_LEVEL environment variable override after loading
    4. Uses Python's native logging configuration - no custom parsing needed!
    
    Args:
        name: Optional name for the logger (defaults to root logger)
    """
    # Set up environment variables for INI file substitution
    _setup_environment_variables()
    
    # Find the logging configuration file
    config_path = _find_logging_config()
    
    if config_path is None:
        # Fallback to basic configuration if no INI file found
        print("Warning: No logging.ini file found, using basic logging configuration", file=sys.stderr)
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s: %(name)s: %(message)s',
            stream=sys.stderr
        )
        return
    
    try:
        # Use Python's native INI configuration loader
        logging.config.fileConfig(
            str(config_path),
            disable_existing_loggers=False
        )
        
        # Apply LOG_LEVEL environment variable override
        env_log_level = os.environ.get('LOG_LEVEL')
        if env_log_level and env_log_level.strip():
            env_level = env_log_level.strip().upper()
            if env_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                print(f"LOG_LEVEL environment variable set to: {env_level}", file=sys.stderr)
                # Override root logger and console handler levels
                root_logger = logging.getLogger()
                root_logger.setLevel(getattr(logging, env_level))
                
                # Update console handler level
                for handler in root_logger.handlers:
                    if isinstance(handler, logging.StreamHandler):
                        handler.setLevel(getattr(logging, env_level))
                
                # Override specific logger levels that are commonly used
                specific_loggers = [
                    'pyobcomp.comparison',
                    'multi_eden.run.ai'
                ]
                for logger_name in specific_loggers:
                    specific_logger = logging.getLogger(logger_name)
                    specific_logger.setLevel(getattr(logging, env_level))
        
        # Log that logging has been configured
        if name:
            logger = logging.getLogger(name)
            logger.debug(f"Logging configured for {name} from {config_path}")
        else:
            logging.debug(f"Logging configured for root logger from {config_path}")
            
    except Exception as e:
        # Fallback to basic configuration if INI file is invalid
        print(f"Warning: Failed to load logging config from {config_path}: {e}", file=sys.stderr)
        print("Using basic logging configuration", file=sys.stderr)
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s: %(name)s: %(message)s',
            stream=sys.stderr
        )


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
