"""Secrets management tasks.

Simple task definitions that handle configuration errors with built-in guidance
and delegate to secret_utils for the actual operations."""

import sys
import json
from invoke import task
from multi_eden.build.config.exceptions import ConfigException
from multi_eden.build.secrets.interface import PassphraseRequiredException, InvalidPassphraseException


def _handle_config_error(e: ConfigException):
    """Handle configuration errors with built-in guidance."""
    print(e.guidance, file=sys.stderr)
    sys.exit(1)


def _call_manager_method(operation_name, method_name):
    """Helper to call a manager method with no arguments and handle unsupported providers."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    from multi_eden.build.secrets.secret_utils import create_unsupported_provider_response
    
    try:
        manager = get_secrets_manager()
    except ConfigException as e:
        _handle_config_error(e)
    
    if not hasattr(manager, method_name):
        response = create_unsupported_provider_response(operation_name, manager.manager_type)
        print(response.model_dump_json(indent=2, exclude_none=True))
        sys.exit(1)
    
    response = getattr(manager, method_name)()
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)




@task(help={
    'passphrase': 'Passphrase for local secrets (optional, will prompt if not provided)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
def list(ctx, passphrase=None, quiet=False, debug=False):
    """
    List all secrets in the configured store.
    
    Examples:
        invoke secrets list --config-env=dev
        MULTI_EDEN_ENV=prod invoke secrets list
    """
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    try:
        manager = get_secrets_manager()
        response = manager.list_secrets(passphrase, throw_not_found=True)
    except ConfigException as e:
        _handle_config_error(e)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'secret_name': 'Name of the secret to retrieve',
    'show': 'Show the actual secret value (default: show hash)',
    'passphrase': 'Passphrase for local secrets (optional, will prompt if not provided)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
def get(ctx, secret_name, show=False, passphrase=None, quiet=False, debug=False):
    """
    Get a specific secret value.
    
    Examples:
        invoke secrets get my-secret --config-env=dev
        invoke secrets get my-secret --show --config-env=prod
    """
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    try:
        manager = get_secrets_manager()
        response = manager.get_secret(secret_name, passphrase, show=show)
    except ConfigException as e:
        _handle_config_error(e)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(
    positional=['secret_name', 'secret_value'],
    help={
        'secret_name': 'Name of the secret to set',
        'secret_value': 'Value to store (optional, will prompt if not provided)',
        'passphrase': 'Passphrase for local secrets (optional, will prompt if not provided)',
        'quiet': 'Suppress configuration display',
        'debug': 'Enable debug logging'
    }
)
def set(ctx, secret_name, secret_value=None, passphrase=None, quiet=False, debug=False):
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
    
    try:
        manager = get_secrets_manager()
        response = manager.set_secret(secret_name, secret_value, passphrase)
    except ConfigException as e:
        _handle_config_error(e)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'secret_name': 'Name of the secret to delete',
    'yes': 'Skip confirmation prompt',
    'passphrase': 'Passphrase for local secrets (optional, will prompt if not provided)',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
def delete(ctx, secret_name, yes=False, passphrase=None, quiet=False, debug=False):
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
    
    try:
        manager = get_secrets_manager()
        response = manager.delete_secret(secret_name, passphrase)
    except ConfigException as e:
        _handle_config_error(e)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'local_repo_folder': 'Local repository folder where secrets will be saved',
    'passphrase': 'Passphrase for encrypted operations',
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
def download(ctx, local_repo_folder, passphrase=None, quiet=False, debug=False):
    """
    Download secrets from the configured store to local encrypted files.
    
    Creates .secrets file in the specified local repository folder with all secrets
    from the specified environment's secret store.
    
    Args:
        local_repo_folder: Path to the local repository folder where secrets will be saved
    
    Examples:
        invoke secrets download /path/to/repo --config-env=dev
        invoke secrets download /path/to/backup --config-env=prod --passphrase=my-passphrase
    """
    from multi_eden.build.secrets.secret_utils import download_secrets_operation
    
    try:
        response = download_secrets_operation(local_repo_folder, None, passphrase=passphrase)
    except ConfigException as e:
        _handle_config_error(e)
    
    print(response.model_dump_json(indent=2, exclude_none=True))
    
    if not response.meta.success:
        sys.exit(1)


@task(help={
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
def get_cached_key(c, quiet=False, debug=False):
    """Show current cached encryption key status and hash."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    from multi_eden.build.secrets.secret_utils import create_unsupported_provider_response
    
    try:
        manager = get_secrets_manager()
    except ConfigException as e:
        _handle_config_error(e)
    
    if not hasattr(manager, 'get_cached_key'):
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
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
def set_cached_key(c, passphrase, quiet=False, debug=False):
    """Generate and cache encryption key from passphrase for local secrets."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    from multi_eden.build.secrets.secret_utils import create_unsupported_provider_response
    
    try:
        manager = get_secrets_manager()
    except ConfigException as e:
        _handle_config_error(e)
    
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
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
def update_key(c, new_passphrase, quiet=False, debug=False):
    """Update encryption key by re-encrypting all secrets with new passphrase."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    from multi_eden.build.secrets.secret_utils import create_unsupported_provider_response
    
    try:
        manager = get_secrets_manager()
    except ConfigException as e:
        _handle_config_error(e)
    
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
    'quiet': 'Suppress configuration display',
    'debug': 'Enable debug logging'
})
def clear(c, force=False, quiet=False, debug=False):
    """Clear all secrets from the configured store."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    try:
        manager = get_secrets_manager()
    except ConfigException as e:
        _handle_config_error(e)
    
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


@task
def clear_cached_key(ctx, quiet=False, debug=False):
    """
    Clear the cached encryption key for local secrets.
    
    This will require providing a passphrase for subsequent operations
    until a new cached key is set.
    """
    _call_manager_method("clear-cached-key", "clear_cached_key")