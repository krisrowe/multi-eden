"""Secrets management tasks.

Simple task definitions that use the @requires_config_env decorator
and delegate to secret_utils for the actual operations."""

import sys
import json
from invoke import task
from multi_eden.build.tasks.config.decorators import requires_config_env
from multi_eden.build.secrets.interface import PassphraseRequiredException, InvalidPassphraseException





@task(help={
    'config_env': 'Configuration environment to use (e.g., dev, local)',
    'passphrase': 'Passphrase for local secrets (optional, will prompt if not provided)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
@requires_config_env
def list(ctx, config_env=None, passphrase=None, quiet=False, debug=False):
    """
    List all secrets in the configured store.
    
    Examples:
        invoke secrets list --config-env=dev
        MULTI_EDEN_ENV=prod invoke secrets list
    """
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    manager = get_secrets_manager()
    response = manager.list_secrets(passphrase)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'secret_name': 'Name of the secret to retrieve',
    'show': 'Show the actual secret value (default: show hash)',
    'config_env': 'Configuration environment to use (e.g., dev, local)',
    'passphrase': 'Passphrase for local secrets (optional, will prompt if not provided)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
@requires_config_env
def get(ctx, secret_name, show=False, config_env=None, passphrase=None, quiet=False, debug=False):
    """
    Get a specific secret value.
    
    Examples:
        invoke secrets get my-secret --config-env=dev
        invoke secrets get my-secret --show --config-env=prod
    """
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    manager = get_secrets_manager()
    response = manager.get_secret(secret_name, passphrase, show=show)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(
    positional=['secret_name', 'secret_value'],
    help={
        'secret_name': 'Name of the secret to set',
        'secret_value': 'Value to store (optional, will prompt if not provided)',
        'config_env': 'Configuration environment to use (e.g., dev, local)',
        'passphrase': 'Passphrase for local secrets (optional, will prompt if not provided)',
        'quiet': 'Suppress configuration display',
        'debug': 'Enable debug logging'
    }
)
@requires_config_env
def set(ctx, secret_name, secret_value=None, config_env=None, passphrase=None, quiet=False, debug=False):
    """
    Set a secret value.
    
    Examples:
        invoke secrets set my-secret "my-value" --config-env=dev
        invoke secrets set my-secret --config-env=prod  # Will prompt for value
    """
    import getpass
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    if secret_value is None:
        secret_value = getpass.getpass(f"Enter value for secret '{secret_name}': ")
        if not secret_value:
            print("❌ Secret value cannot be empty")
            sys.exit(1)
    
    manager = get_secrets_manager()
    response = manager.set_secret(secret_name, secret_value, passphrase)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'secret_name': 'Name of the secret to delete',
    'config_env': 'Configuration environment to use (e.g., dev, local)',
    'yes': 'Skip confirmation prompt',
    'passphrase': 'Passphrase for local secrets (optional, will prompt if not provided)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
@requires_config_env
def delete(ctx, secret_name, config_env=None, yes=False, passphrase=None, quiet=False, debug=False):
    """
    Delete a secret.
    
    Examples:
        invoke secrets delete my-secret --config-env=dev
        invoke secrets delete my-secret --yes --config-env=prod
    """
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    # Interactive confirmation unless --yes
    if not yes:
        response = input(f"Delete secret '{secret_name}'? Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            print("❌ Operation cancelled")
            sys.exit(1)
    
    manager = get_secrets_manager()
    response = manager.delete_secret(secret_name, passphrase)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'output_dir': 'Output directory for downloaded secrets (default: current directory)',
    'config_env': 'Configuration environment to use (e.g., dev, local)',
    'passphrase': 'Passphrase for encrypted operations',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
@requires_config_env
def download(ctx, config_env=None, output_dir='.', passphrase=None, quiet=False, debug=False):
    """
    Download secrets from the configured store to local encrypted files.
    
    Creates .secrets/[env-name] file in the output directory with all secrets
    from the specified environment's secret store.
    
    Examples:
        invoke secrets download --config-env=dev
        invoke secrets download --config-env=prod --output-dir=/path/to/backup
    """
    from multi_eden.build.secrets.secret_utils import download_secrets_operation
    
    response = download_secrets_operation(output_dir, config_env, passphrase=passphrase)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'config_env': 'Configuration environment to use (e.g., dev, local)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
@requires_config_env
def get_cached_key(c, config_env=None, quiet=False, debug=False):
    """Show current cached encryption key status and hash."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    from multi_eden.build.secrets.secret_utils import create_unsupported_provider_response
    
    manager = get_secrets_manager()
    
    # Only works with local manager
    if manager.manager_type != "local":
        response = create_unsupported_provider_response("get-cached-key", manager.manager_type)
        print(response.model_dump_json(indent=2, exclude_none=True))
        sys.exit(1)
    
    response = manager.get_cached_key()
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    # get-cached-key always succeeds - it's just reporting status
    # Only exit with error code for actual errors (not KEY_NOT_SET)
    if not response.meta.success and response.meta.error and response.meta.error.code != "KEY_NOT_SET":
        sys.exit(1)


@task(help={
    'passphrase': 'Passphrase to generate encryption key from',
    'config_env': 'Configuration environment to use (e.g., dev, local)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
@requires_config_env
def set_cached_key(c, passphrase, config_env=None, quiet=False, debug=False):
    """Generate and cache encryption key from passphrase for local secrets."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    from multi_eden.build.secrets.secret_utils import create_unsupported_provider_response
    
    manager = get_secrets_manager()
    
    # Only works with local manager
    if manager.manager_type != "local":
        response = create_unsupported_provider_response("set-cached-key", manager.manager_type)
        print(response.model_dump_json(indent=2, exclude_none=True))
        sys.exit(1)
    
    response = manager.set_cached_key(passphrase)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'new_passphrase': 'New passphrase to use for encryption',
    'config_env': 'Configuration environment to use (e.g., dev, local)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
@requires_config_env
def update_key(c, new_passphrase, config_env=None, quiet=False, debug=False):
    """Update encryption key by re-encrypting all secrets with new passphrase."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    from multi_eden.build.secrets.secret_utils import create_unsupported_provider_response
    
    manager = get_secrets_manager()
    
    # Only works with local manager
    if manager.manager_type != "local":
        response = create_unsupported_provider_response("update-key", manager.manager_type)
        print(response.model_dump_json(indent=2, exclude_none=True))
        sys.exit(1)
    
    response = manager.update_encryption_key(new_passphrase)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'force': 'Skip confirmation prompt and force clear all secrets',
    'config_env': 'Configuration environment to use (e.g., dev, local)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
@requires_config_env
def clear(c, force=False, config_env=None, quiet=False, debug=False):
    """Clear all secrets from the configured store."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    manager = get_secrets_manager()
    
    # Interactive confirmation unless --force
    if not force:
        print(f"⚠️  This will permanently delete ALL secrets in {manager.manager_type} store.", file=sys.stderr)
        response = input("Type 'yes' to confirm: ")
        if response.lower() != 'yes':
            from multi_eden.build.secrets.models import ClearSecretsResponse, SecretsManagerMetaResponse, ErrorInfo
            cancelled_response = ClearSecretsResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=manager.manager_type,
                    operation="clear",
                    error=ErrorInfo(code="CANCELLED", message="Operation cancelled by user")
                ),
                cleared_count=0
            )
            print(cancelled_response.model_dump_json(indent=2))
            sys.exit(1)
    
    response = manager.clear_all_secrets()
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)
