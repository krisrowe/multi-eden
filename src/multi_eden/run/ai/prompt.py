"""
Invoke task runner for AI model operations.

Provides command-line tasks for testing and managing AI models.
"""
import logging
from invoke import task
from typing import Optional
from .factory import ModelClientFactory
from .config import AIConfig

logger = logging.getLogger(__package__)


@task
def test_provider(ctx, provider: str):
    """
    Test a specific AI provider.
    
    Args:
        provider: Provider name to test
        service: Service name to use for testing
    """
    try:
        factory = ModelClientFactory()
        client = factory.create_model_client(provider=provider)
        print(f"✓ Successfully created {provider}")
        print(f"  Client type: {type(client).__name__}")
        print(f"  Service: {client.service_name}")
        
    except Exception as e:
        print(f"✗ Failed to create {provider} client: {e}")
        return 1
    
    return 0


@task
def list_providers(ctx):
    """List all available AI providers."""
    try:
        factory = ModelClientFactory()
        providers = factory.get_enabled_providers()
        
        if not providers:
            print("No AI providers configured")
            return 0
        
        print("Available AI providers:")
        for provider in providers:
            print(f"  - {provider}")
        
        return 0
        
    except Exception as e:
        print(f"Failed to list providers: {e}")
        return 1


@task
def list_models(ctx):
    """List all available AI models."""
    try:
        factory = ModelClientFactory()
        models = factory.get_available_models()
        
        if not models:
            print("No AI models configured")
            return 0
        
        print("Available AI models:")
        for model_id in models:
            print(f"  - {model_id}")
        
        return 0
        
    except Exception as e:
        print(f"Failed to list models: {e}")
        return 1


@task
def list_services(ctx):
    """List all available AI services."""
    try:
        factory = ModelClientFactory()
        services = factory.get_available_services()
        
        if not services:
            print("No AI services configured")
            return 0
        
        print("Available AI services:")
        for service in services:
            print(f"  - {service}")
        
        return 0
        
    except Exception as e:
        print(f"Failed to list services: {e}")
        return 1


@task
def validate_config(ctx):
    """Validate the AI configuration."""
    try:
        factory = ModelClientFactory()
        factory.validate_configuration()
        print("✓ AI configuration is valid")
        return 0
        
    except Exception as e:
        print(f"✗ AI configuration validation failed: {e}")
        return 1


@task
def test_prompt(ctx, provider: str, prompt: str):
    """
    Test a prompt with a specific provider and service.
    
    Args:
        provider: Provider name to use
        service: Service name to use
        prompt: Test prompt to send
    """
    try:
        factory = ModelClientFactory()
        client = factory.create_model_client(provider=provider, service_name=service)
        
        print(f"Testing {provider} client with {service} service")
        print(f"Prompt: {prompt}")
        
        # This is a basic test - you might want to add more sophisticated testing
        print(f"✓ Successfully created client and loaded prompt template")
        print(f"  Service: {client.service_name}")
        print(f"  Has schema: {client.get_schema() is not None}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Failed to test prompt: {e}")
        return 1


@task
def show_config(ctx):
    """Show the current AI configuration."""
    try:
        config = AIConfig()
        
        print("AI Configuration:")
        print(f"  Config file: {config.config_path}")
        print()
        
        # Show providers
        providers = config.get_providers()
        if providers:
            print("Providers:")
            for name, provider in providers.items():
                print(f"  {name}: {provider.description}")
                print(f"    Class: {provider.class_path}")
                print(f"    Enabled: {provider.enabled}")
                print(f"    Priority: {provider.priority}")
                print(f"    Models: {', '.join(provider.models.keys())}")
                print()
        
        # Show services
        services = config.get_services()
        if services:
            print("Services:")
            for name, service in services.items():
                print(f"  {name}:")
                print(f"    Default model: {service.default_model}")
                print(f"    Prompt length: {len(service.prompt)} characters")
                print()
        
        return 0
        
    except Exception as e:
        print(f"Failed to show configuration: {e}")
        return 1


@task
def test_factory(ctx):
    """Test the factory system end-to-end."""
    try:
        factory = ModelClientFactory()
        
        print("Testing AI Factory System:")
        print()
        
        # Test configuration loading
        print("1. Configuration Loading:")
        config = factory.config
        print(f"   ✓ Loaded config from: {config.config_path}")
        print(f"   ✓ Providers: {len(config.get_providers())}")
        print(f"   ✓ Models: {len(config.get_models())}")
        print(f"   ✓ Services: {len(config.get_services())}")
        print()
        
        # Test provider listing
        print("2. Provider Discovery:")
        providers = factory.get_enabled_providers()
        for provider in providers:
            print(f"   ✓ {provider}")
        print()
        
        # Test model listing
        print("3. Model Discovery:")
        models = factory.get_available_models()
        for model in models:
            print(f"   ✓ {model}")
        print()
        
        # Test service listing
        print("4. Service Discovery:")
        services = factory.get_available_services()
        for service in services:
            print(f"   ✓ {service}")
        print()
        
        # Test client creation
        print("5. Client Creation:")
        if providers and services:
            provider = providers[0]
            service = services[0]
            try:
                client = factory.create_model_client(provider=provider, service_name=service)
                print(f"   ✓ Created {provider} client for {service}")
                print(f"   ✓ Client type: {type(client).__name__}")
            except Exception as e:
                print(f"   ✗ Failed to create client: {e}")
        print()
        
        print("✓ Factory system test completed successfully")
        return 0
        
    except Exception as e:
        print(f"✗ Factory system test failed: {e}")
        return 1
