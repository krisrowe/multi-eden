"""
Prompt task for AI interactions.

This module provides a task for interacting with AI models using the consolidated
environment configuration.
"""

import sys
from pathlib import Path
from invoke import task
from multi_eden.build.tasks.config.decorators import requires_config_env


@task(help={
    'config_env': 'Configuration environment to use (required for project_id)',
    'model': 'AI model to use (default: gemini)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging (sets LOG_LEVEL=DEBUG)'
})
@requires_config_env
def prompt(ctx, prompt_text, config_env=None, model='gemini', quiet=False, debug=False):
    """
    Send a prompt to an AI model.
    
    Examples:
        invoke prompt --message="What is the capital of France?"
        invoke prompt --message="Explain quantum computing" --config-env=static
        echo "Hello AI" | invoke prompt --message=-
    """
    
    # Get message from stdin if prompt_text is '-'
    if prompt_text == '-':
        prompt_text = sys.stdin.read().strip()
    
    print(f"🤖 Sending prompt to {model.upper()} model...", file=sys.stderr)
    print(f"💬 Prompt: {prompt_text}", file=sys.stderr)
    
    # Import model client and send the prompt
    try:
        from multi_eden.run.ai.factory import create
        
        # Get model client for the default service
        model_client = create('default')
        
        # Send the prompt
        response = model_client.process_prompt(prompt_text)
        
        # Output the pristine AI response to stdout
        print(response)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to send prompt: {e}", file=sys.stderr)
        return False
