"""
Reusable AI task decorator and utilities.

This module provides a decorator that combines @requires_config_env with
common AI task patterns, enabling consistent task signatures and behavior
across prompt, analyze, and segment tasks.
"""

import sys
from functools import wraps
from invoke import task
from .config.decorators import requires_config_env


def ai_task(help_dict=None):
    """
    Decorator for AI tasks that combines @requires_config_env with common AI patterns.
    
    This decorator provides:
    - Automatic environment configuration loading
    - Consistent parameter handling (prompt as positional arg, optional --model)
    - Standard help text patterns
    - Error handling
    
    Args:
        help_dict: Optional dictionary of help text for parameters
        
    Usage:
        @ai_task({
            'prompt_text': 'The prompt to send to the AI model',
            'model': 'AI model to use (overrides service default)'
        })
        def my_ai_task(ctx, prompt_text, model=None, config_env=None, debug=False):
            # Your AI task implementation
            pass
    """
    def decorator(func):
        # Build default help text
        default_help = {
            'config_env': 'Configuration environment to use (e.g., dev, prod)',
            'model': 'AI model to use (overrides service default)',
            'debug': 'Enable debug logging (sets LOG_LEVEL=DEBUG)'
        }
        
        # Merge with custom help text
        if help_dict:
            default_help.update(help_dict)
        
        # Apply decorators in correct order: @task first, then @requires_config_env
        @task(help=default_help)
        @requires_config_env
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def run_ai_service(service_class, prompt_text, model=None, **service_kwargs):
    """
    Helper function to run an AI service with consistent error handling.
    
    Args:
        service_class: The AI service class to instantiate (e.g., PromptService)
        prompt_text: The prompt text to send to the service
        model: Optional model override
        **service_kwargs: Additional kwargs to pass to service constructor
        
    Returns:
        The service response object
    """
    try:
        # Create service instance with optional model override
        service = service_class(model_override=model, **service_kwargs)
        
        # Process the prompt
        response = service.process(prompt_text)
        
        return response
        
    except Exception as e:
        print(f"❌ AI service failed: {e}", file=sys.stderr)
        sys.exit(1)


def print_ai_response(response, format='text'):
    """
    Helper function to print AI responses in a consistent format.
    
    Args:
        response: The AI service response object
        format: Output format ('text', 'json')
    """
    if format == 'json':
        import json
        print(json.dumps(response.model_dump(), indent=2))
    else:
        # For text format, extract the main content
        if hasattr(response, 'content'):
            # Generic prompt response
            print(response.content)
        elif hasattr(response, 'items'):
            # Segmentation response
            for item in response.items:
                print(f"• {item}")
        else:
            # Fallback to JSON for complex responses
            import json
            print(json.dumps(response.model_dump(), indent=2))
