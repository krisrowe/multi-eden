"""
Unified Runtime Settings Management

Provides runtime access to all configuration settings via get_setting(name).
Uses a manifest-driven approach with proper error handling, secret masking, and caching.
Replaces both the old settings.py and secrets.py modules.
"""
import os
import sys
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SettingNotDefinedException(Exception):
    """Raised when a setting name is not defined in the manifest."""
    
    def __init__(self, setting_name: str, available_settings: List[str]):
        self.setting_name = setting_name
        self.available_settings = available_settings
        super().__init__(
            f"Setting '{setting_name}' is not defined in the settings manifest. "
            f"Available settings: {', '.join(sorted(available_settings))}"
        )


class SettingValueNotFoundException(Exception):
    """Raised when a setting is defined but its value cannot be found."""
    
    def __init__(self, setting_name: str, source: str, details: str = ""):
        self.setting_name = setting_name
        self.source = source
        self.details = details
        message = f"Setting '{setting_name}' is defined but value not found from source '{source}'"
        if details:
            message += f": {details}"
        super().__init__(message)


@dataclass
class SettingDefinition:
    """Definition of a runtime setting from the manifest."""
    name: str
    source: str
    secret: bool
    description: str
    required: bool = True
    stub_indicator: Optional[Dict[bool, str]] = None


# Global cache for settings manifest and values
_settings_manifest: Optional[List[SettingDefinition]] = None
_settings_cache: Dict[str, Any] = {}
_app_config_cache: Optional[Dict[str, Any]] = None


def _load_settings_manifest() -> List[SettingDefinition]:
    """Load and cache the settings manifest from YAML."""
    global _settings_manifest
    
    if _settings_manifest is not None:
        return _settings_manifest
    
    # Find the manifest file
    manifest_path = Path(__file__).parent / "settings_manifest.yaml"
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"Settings manifest not found at {manifest_path}")
    
    try:
        with open(manifest_path, 'r') as f:
            manifest_data = yaml.safe_load(f)
        
        if not isinstance(manifest_data, dict) or 'settings' not in manifest_data:
            raise ValueError("Invalid manifest format: missing 'settings' key")
        
        settings_list = []
        for setting_data in manifest_data['settings']:
            setting = SettingDefinition(
                name=setting_data['name'],
                source=setting_data['source'],
                secret=setting_data.get('secret', False),
                description=setting_data.get('description', ''),
                required=setting_data.get('required', True),
                stub_indicator=setting_data.get('stub-indicator')
            )
            settings_list.append(setting)
        
        _settings_manifest = settings_list
        logger.debug(f"Loaded {len(settings_list)} settings from manifest")
        return _settings_manifest
        
    except Exception as e:
        raise RuntimeError(f"Failed to load settings manifest: {e}")


def _load_app_config() -> Dict[str, Any]:
    """Load and cache the app configuration from config/app.yaml."""
    global _app_config_cache
    
    if _app_config_cache is not None:
        return _app_config_cache
    
    # Look for app.yaml in the current working directory
    app_config_path = Path.cwd() / 'config' / 'app.yaml'
    
    if not app_config_path.exists():
        # Generate default app config based on package name
        package_name = __name__.split('.')[0]  # 'multi_eden'
        default_app_id = package_name.replace('_', '-') + '-default'
        _app_config_cache = {'id': default_app_id}
        logger.debug(f"app.yaml not found, using default app ID: {default_app_id}")
        return _app_config_cache
    
    try:
        with open(app_config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        if not isinstance(config_data, dict):
            raise ValueError("app.yaml must contain a dictionary")
        
        _app_config_cache = config_data
        logger.debug(f"Loaded app config from {app_config_path}")
        return _app_config_cache
        
    except Exception as e:
        # Fall back to default on any error
        package_name = __name__.split('.')[0]
        default_app_id = package_name.replace('_', '-') + '-default'
        _app_config_cache = {'id': default_app_id}
        logger.debug(f"Failed to load app.yaml ({e}), using default app ID: {default_app_id}")
        return _app_config_cache


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Get a nested value from a dictionary using dot notation."""
    keys = path.split('.')
    current = data
    
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise KeyError(f"Path '{path}' not found")
        current = current[key]
    
    return current


def _load_setting_value(setting: SettingDefinition) -> Any:
    """Load a setting value from its source."""
    source_type, source_param = setting.source.split(':', 1)
    
    if source_type == 'env-var':
        value = os.environ.get(source_param)
        if value is None:
            if setting.required:
                raise SettingValueNotFoundException(
                    setting.name, 
                    setting.source, 
                    f"Environment variable '{source_param}' not set"
                )
            return None
        return value.strip() if value else value
    
    elif source_type == 'app-config':
        app_config = _load_app_config()
        try:
            value = _get_nested_value(app_config, source_param)
            return value
        except KeyError:
            if setting.required:
                raise SettingValueNotFoundException(
                    setting.name,
                    setting.source,
                    f"Path '{source_param}' not found in app.yaml"
                )
            return None
    
    elif source_type == 'computed':
        # For future extension - computed values
        raise NotImplementedError(f"Computed source type not yet implemented: {setting.source}")
    
    else:
        raise ValueError(f"Unknown source type '{source_type}' for setting '{setting.name}'")


def get_setting(name: str) -> str:
    """
    Get a setting value by name.
    
    Args:
        name: The setting name (e.g., 'jwt-secret-key', 'app-id')
        
    Returns:
        The setting value as a string
        
    Raises:
        SettingNotDefinedException: If the setting name is not in the manifest
        SettingValueNotFoundException: If the setting is defined but value not found
    """
    # Check cache first
    if name in _settings_cache:
        return _settings_cache[name]
    
    # Load manifest
    manifest = _load_settings_manifest()
    
    # Find the setting definition
    setting_def = None
    for setting in manifest:
        if setting.name == name:
            setting_def = setting
            break
    
    if setting_def is None:
        available_names = [s.name for s in manifest]
        raise SettingNotDefinedException(name, available_names)
    
    # Load the value
    value = _load_setting_value(setting_def)
    
    # Cache the value
    _settings_cache[name] = value
    
    return value


def list_settings() -> List[Dict[str, Any]]:
    """
    List all available settings with their metadata.
    
    Returns:
        List of setting information dictionaries
    """
    manifest = _load_settings_manifest()
    settings_info = []
    
    for setting in manifest:
        try:
            value = get_setting(setting.name)
            # Mask secrets for display
            display_value = "***MASKED***" if setting.secret else value
        except SettingValueNotFoundException:
            display_value = "<NOT SET>"
        except Exception as e:
            display_value = f"<ERROR: {e}>"
        
        settings_info.append({
            'name': setting.name,
            'value': display_value,
            'source': setting.source,
            'secret': setting.secret,
            'description': setting.description,
            'required': setting.required
        })
    
    return settings_info


def print_settings_table(file=None):
    """
    Print a formatted table of settings to stderr (or specified file).
    
    Args:
        file: File object to write to (defaults to sys.stderr)
    """
    if file is None:
        file = sys.stderr
    
    settings_info = list_settings()
    
    print("\n" + "=" * 85, file=file)
    print("🔧 RUNTIME SETTINGS", file=file)
    print("=" * 85, file=file)
    print(f"{'SETTING':<25} {'VALUE':<34} {'SOURCE':<19}", file=file)
    print("-" * 85, file=file)
    
    for setting in settings_info:
        # Truncate long values for display
        display_value = str(setting['value']) if setting['value'] is not None else "<NOT SET>"
        if len(display_value) > 34:
            display_value = display_value[:31] + "..."
        
        # Truncate long source for display
        display_source = setting['source']
        if len(display_source) > 19:
            display_source = display_source[:16] + "..."
        
        print(f"{setting['name']:<25} {display_value:<34} {display_source:<19}", file=file)
    
    print("=" * 85, file=file)


def clear_cache():
    """Clear all cached settings and manifest data. Useful for testing."""
    global _settings_manifest, _settings_cache, _app_config_cache
    _settings_manifest = None
    _settings_cache.clear()
    _app_config_cache = None


# Legacy compatibility functions - these will be deprecated
def get_secret(secret_name: str) -> str:
    """
    Legacy compatibility function for get_secret().
    
    DEPRECATED: Use get_setting() instead.
    """
    import warnings
    warnings.warn(
        "get_secret() is deprecated. Use get_setting() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_setting(secret_name)


def get_app_id() -> str:
    """Get the application ID."""
    return get_setting('app-id')


def is_project_id_set() -> bool:
    """Check if a project ID is configured.
    
    Returns:
        True if project ID is set, False otherwise
    """
    try:
        project_id = get_setting('project-id')
        return bool(project_id and project_id.strip())
    except SettingValueNotFoundException:
        return False


def is_cloud_run() -> bool:
    """Check if running in Google Cloud Run.
    
    Returns:
        True if running in Cloud Run, False otherwise
    """
    return os.environ.get('K_SERVICE') is not None


def get_project_id() -> str:
    """Get the Google Cloud project ID.
    
    Returns:
        Project ID string
        
    Raises:
        SettingValueNotFoundException: If project ID is not configured
    """
    return get_setting('project-id')


def is_secrets_available() -> bool:
    """Check if secrets are available and can be loaded.
    
    Returns:
        True if secrets can be loaded successfully, False otherwise.
    """
    try:
        # Try to load a required secret to test availability
        get_setting('jwt-secret-key')
        return True
    except SettingValueNotFoundException:
        return False


def get_authorization():
    """Get authorization configuration (backward compatibility wrapper).
    
    Returns:
        Authorization instance loaded from settings.
    """
    from ..auth.config import get_authorization_config
    return get_authorization_config()


def is_setting_available(name: str) -> bool:
    """Check if a setting is available without raising an exception."""
    try:
        get_setting(name)
        return True
    except Exception:
        return False


def _clear_settings_cache():
    """Clear the settings cache for testing purposes."""
    global _settings_cache
    _settings_cache = {}


def print_settings():
    """Print formatted settings table to stderr showing name, value, and source."""
    import sys
    
    # ANSI color codes
    GRAY = '\033[90m'    # Dark gray for unavailable settings
    YELLOW = '\033[93m'  # Bright yellow for secrets (highly visible)
    RESET = '\033[0m'
    
    print("="*68, file=sys.stderr)
    print("📋 Runtime Configuration Settings", file=sys.stderr)
    print("="*68, file=sys.stderr)
    print(f"{'Setting Name':<25} {'Value':<28} {'Source':<15}", file=sys.stderr)
    print("-"*68, file=sys.stderr)
    
    # Get all settings from manifest
    manifest_settings = _load_settings_manifest()
    
    for setting_def in manifest_settings:
        name = setting_def.name
        # Determine source first (always available from manifest)
        if setting_def.source.startswith('env-var:'):
            source = "Environment"
        elif setting_def.source == 'app-yaml':
            source = "App Config"
        else:
            source = "Other"
            
        # Check if setting is available first
        if is_setting_available(name):
            value = get_setting(name)
            # Handle secrets with partial display
            if setting_def.secret:
                if value:
                    # Show first 6 characters + ellipsis in bright yellow
                    display_value = f"{YELLOW}{str(value)[:6]}...{RESET}"
                else:
                    display_value = "(not set)"
            else:
                display_value = str(value) if value is not None else "(not set)"
        else:
            # Use softer gray color for unavailable settings
            display_value = f"{GRAY}(not available){RESET}"
            
        # Handle formatting with color codes - they don't count toward visible width
        if GRAY in display_value or YELLOW in display_value:
            # For colored text, calculate visible length and add manual padding
            visible_text = display_value.replace(GRAY, '').replace(YELLOW, '').replace(RESET, '')
            padding_needed = 28 - len(visible_text)
            padded_value = display_value + ' ' * padding_needed
            print(f"{name:<25} {padded_value} {source:<15}", file=sys.stderr)
        else:
            # Normal formatting for non-colored text
            print(f"{name:<25} {display_value:<28} {source:<15}", file=sys.stderr)
    
    print("="*68, file=sys.stderr)
    print("", file=sys.stderr)


def get_settings_with_stub_indicators() -> List[SettingDefinition]:
    """Get all settings that have stub-indicator configuration."""
    manifest = _load_settings_manifest()
    stub_settings = [setting for setting in manifest if setting.stub_indicator is not None]
    return stub_settings


def print_stub_usage_table():
    """Print stub usage table showing provider configurations from settings manifest."""
    import sys
    
    try:
        stub_settings = get_settings_with_stub_indicators()
        
        if not stub_settings:
            return
            
        print("\n" + "="*60, file=sys.stderr)
        print("🔧 STUB USAGE", file=sys.stderr)
        print("="*60, file=sys.stderr)
        print(f"{'Type':<20} {'Usage':<8} {'Provider':<30}", file=sys.stderr)
        print("-"*60, file=sys.stderr)
        
        for setting in stub_settings:
            stub_info = setting.stub_indicator
            setting_type = stub_info['type']
            
            # Get current value
            if is_setting_available(setting.name):
                current_value = get_setting(setting.name)
                # Convert to boolean if it's a string
                if isinstance(current_value, str):
                    current_value = current_value.lower() in ('true', '1', 'yes')
                
                # Get the usage and provider based on current value
                if current_value:
                    # Stub mode - use dim gray for True
                    usage = "\033[2mStub\033[0m"
                    provider = stub_info.get(True, 'Enabled')
                else:
                    # Real mode - use bright white for False
                    usage = "\033[1mReal\033[0m"
                    provider = stub_info.get(False, 'Disabled')
            else:
                usage = "\033[90m?\033[0m"  # Gray for unknown
                provider = "(not available)"
            
            # Handle alignment with color codes - calculate visible length and add manual padding
            visible_usage = usage.replace('\033[2m', '').replace('\033[1m', '').replace('\033[90m', '').replace('\033[0m', '')
            usage_padding = 8 - len(visible_usage)
            padded_usage = usage + ' ' * usage_padding
            
            print(f"{setting_type:<20} {padded_usage} {provider:<30}", file=sys.stderr)
        
        print("="*60, file=sys.stderr)
        print("", file=sys.stderr)
        
    except Exception as e:
        # If we can't show stub usage table, continue without it
        print(f"⚠️  Could not display stub usage table: {e}", file=sys.stderr)
        print("", file=sys.stderr)


def print_runtime_config():
    """Print complete runtime configuration including settings and stub usage tables."""
    print_settings()
    print_stub_usage_table()
