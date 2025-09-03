"""
Prompt task for AI interactions.

This module provides a task for interacting with AI models using the consolidated
environment configuration.
"""

import sys
from pathlib import Path
from invoke import task
from multi_eden.build.config.loading import load_env as load_env_dynamic


@task(help={
    'prompt_text': 'The prompt to send to the AI model',
    'config_env': 'Configuration environment to use (e.g., dev, local)',
    'model': 'AI model to use (default: gemini-2.5-flash)',
    'grounding': 'Enable Google Search grounding for the prompt',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging (sets LOG_LEVEL=DEBUG)'
})
def prompt(ctx, prompt_text, config_env=None, model='gemini-2.5-flash', grounding=False, quiet=False, debug=False):
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
    
    # Use PromptService directly
    try:
        from multi_eden.run.ai.prompt_service import PromptService
        
        # Create prompt service with model override and grounding
        service = PromptService(model_override=model, enable_grounding=grounding)
        
        # Send the prompt
        response = service.process(prompt_text)
        
        # Output the AI response content to stdout (pipe-friendly)
        if hasattr(response, 'content'):
            print(response.content)
        else:
            print(str(response))
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to send prompt: {e}", file=sys.stderr)
        return False
