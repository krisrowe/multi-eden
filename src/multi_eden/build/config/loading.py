"""
Dynamic environment loading system using loading.yaml configuration.

This system allows for flexible, configurable layering of environment variables
from multiple sources with customizable priority and conditions.
"""

import os
import sys
import logging
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from string import Template

logger = logging.getLogger(__name__)


class LoadingLayer:
    """Represents a single layer in the environment loading process."""
    
    def __init__(self, config: Dict[str, Any]):
        self.name = config['name']
        self.file = config.get('file')
        self.path = config.get('path')
        self.condition = config.get('condition')
        self.layer_type = config.get('type', 'file')
        self.description = config.get('description', '')
    
    def should_load(self, context: Dict[str, Any]) -> bool:
        """Check if this layer should be loaded based on condition."""
        if not self.condition:
            return True
        
        # Simple condition evaluation (can be extended)
        try:
            return eval(self.condition, {"__builtins__": {}}, context)
        except Exception as e:
            logger.warning(f"Failed to evaluate condition '{self.condition}' for layer '{self.name}': {e}")
            return False
    
    def load_values(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load values from this layer."""
        if self.layer_type == 'callback':
            return self._load_from_callback(context)
        else:
            return self._load_from_file(context)
    
    def _load_from_file(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load values from a YAML file."""
        if not self.file or not self.path:
            return {}
        
        try:
            # Resolve file path
            file_path = self._resolve_file_path(self.file)
            if not file_path.exists():
                logger.debug(f"File not found for layer '{self.name}': {file_path}")
                return {}
            
            # Load YAML file
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            # Resolve path within YAML
            resolved_path = self._resolve_yaml_path(self.path, context)
            values = self._get_nested_value(data, resolved_path)
            
            if not isinstance(values, dict):
                logger.debug(f"Path '{resolved_path}' in layer '{self.name}' does not contain a dictionary")
                return {}
            
            logger.debug(f"Loaded {len(values)} values from layer '{self.name}'")
            return values
            
        except Exception as e:
            logger.warning(f"Failed to load layer '{self.name}': {e}")
            return {}
    
    def _process_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """Process value with different source schemes (secret:, task-func:, etc.)."""
        if not isinstance(value, str):
            return value
        
        if value.startswith('secret:'):
            secret_name = value[7:]  # Remove 'secret:' prefix
            return self._get_secret_from_manager(secret_name)
        elif value.startswith('task-func:'):
            func_name = value[10:]  # Remove 'task-func:' prefix
            return self._get_task_function_value(func_name, context)
        else:
            return value
    
    def _get_task_function_value(self, func_name: str, context: Dict[str, Any]) -> str:
        """Execute task function and return its value."""
        dynamics = context.get('dynamics', {})
        
        if func_name not in dynamics:
            raise ValueError(f"Function not found in dynamics: {func_name}")
        
        try:
            func = dynamics[func_name]
            if not callable(func):
                raise ValueError(f"Not a callable function: {func_name}")
            
            # Execute function
            result = func()
            
            # Handle different return types
            if isinstance(result, list) and result:
                # Assume first item is the value we want
                return str(result[0][1]) if len(result[0]) > 1 else str(result[0])
            elif isinstance(result, str):
                return result
            else:
                return str(result)
                
        except Exception as e:
            raise ValueError(f"Task function execution failed: {e}")
    
    def _get_secret_from_manager(self, secret_name: str) -> str:
        """Load secret from configured secrets manager."""
        try:
            from multi_eden.build.secrets.factory import get_secrets_manager
            secrets_manager = get_secrets_manager()
            
            logger.debug(f"Loading secret '{secret_name}' from secrets manager")
            response = secrets_manager.get_secret(secret_name, show=True)
            
            if response.meta.success and response.secret:
                return response.secret.value
            else:
                error_msg = response.meta.error.message if response.meta.error else "Unknown error"
                raise ValueError(f"Failed to load secret '{secret_name}': {error_msg}")
                
        except Exception as e:
            raise ValueError(f"Failed to load secret '{secret_name}' from secrets manager: {e}")
    
    def _resolve_file_path(self, file_path: str) -> Path:
        """Resolve file path to absolute path."""
        if os.path.isabs(file_path):
            return Path(file_path)
        
        # Handle {cwd}/ prefix for current working directory paths
        if file_path.startswith('{cwd}/'):
            cwd_relative_path = file_path[6:]  # Remove '{cwd}/' prefix
            return Path.cwd() / cwd_relative_path
        
        # All other paths are relative to the loading.yaml file location
        return Path(__file__).parent / file_path
    
    def _resolve_yaml_path(self, path_template: str, context: Dict[str, Any]) -> str:
        """Resolve YAML path template with context variables."""
        try:
            # Use string format instead of Template for {} syntax
            return path_template.format(**context)
        except Exception as e:
            logger.warning(f"Failed to resolve path template '{path_template}': {e}")
            return path_template
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value from dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class DynamicEnvironmentLoader:
    """Dynamic environment loader using loading.yaml configuration."""
    
    def __init__(self, config_file: str = None):
        """Initialize the loader with configuration file."""
        if config_file is None:
            config_file = Path(__file__).parent / "loading.yaml"
        
        self.config_file = Path(config_file)
        self.layers = []
        self.settings = {}
        self._load_config()
    
    def _load_config(self):
        """Load the loading.yaml configuration."""
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            # Load layers (preserve YAML order)
            layers_config = config.get('layers', [])
            self.layers = [LoadingLayer(layer_config) for layer_config in layers_config]
            
            # Load settings
            self.settings = config.get('settings', {})
            
            logger.debug(f"Loaded {len(self.layers)} layers from {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration from {self.config_file}: {e}")
            raise
    
    def load_environment(self, 
                        env_name: Optional[str] = None,
                        test_mode: Optional[str] = None,
                        task_name: Optional[str] = None,
                        dynamics: Optional[Dict[str, Callable]] = None,
                        quiet: bool = False) -> Dict[str, Tuple[str, str]]:
        """
        Load environment variables using the configured layers.
        
        Returns:
            Dict mapping variable names to (value, source) tuples
        """
        # Build context for layer evaluation
        context = {
            'env_name': env_name,
            'test_mode': test_mode,
            'task_name': task_name,
            'dynamics': dynamics
        }
        
        # Track loaded variables: name -> (value, source)
        loaded_vars = {}
        
        # Process layers in YAML order (later layers overwrite earlier ones)
        for layer in self.layers:
            if not layer.should_load(context):
                logger.debug(f"Skipping layer '{layer.name}' due to condition")
                continue
            
            try:
                layer_values = layer.load_values(context)
                
                # Merge layer values (later layers overwrite earlier layers)
                for key, value in layer_values.items():
                    env_var_name = key.upper()
                    # Process value (handle secret:, task-func:, etc.)
                    processed_value = layer._process_value(value, context)
                    loaded_vars[env_var_name] = (processed_value, layer.name)
                    logger.debug(f"Layer '{layer.name}' set {env_var_name}={processed_value}")
                
            except Exception as e:
                logger.warning(f"Failed to process layer '{layer.name}': {e}")
        
        # Process loaded variables and set environment variables
        processed_vars = []
        failed_vars = []
        
        for name, (value, source) in loaded_vars.items():
            try:
                # Check if environment variable already exists (highest priority)
                if self.settings.get('env_var_override', True) and name in os.environ:
                    env_value = os.environ[name]
                    processed_vars.append((name, env_value, 'env-var'))
                    logger.debug(f"Using existing {name}={env_value} (from env-var)")
                    continue
                
                # Handle secret: prefix
                if isinstance(value, str) and value.startswith('secret:'):
                    secret_name = value[7:]  # Remove 'secret:' prefix
                    value = self._get_secret_from_manager(secret_name)
                    source = 'secret'
                
                # Convert value to string for environment variable
                if isinstance(value, bool):
                    env_value = 'true' if value else 'false'
                else:
                    env_value = str(value)
                
                # Set environment variable
                os.environ[name] = env_value
                processed_vars.append((name, env_value, source))
                logger.debug(f"Set {name}={env_value} (from {source})")
                
            except Exception as e:
                failed_vars.append((name, e))
                logger.debug(f"Failed to process {name}: {e}")
        
        # Display results if not quiet
        if not quiet and self.settings.get('display_loaded_vars', True):
            self._display_results(processed_vars, failed_vars, context)
        
        return {name: (value, source) for name, value, source in processed_vars}
    
    def _get_secret_from_manager(self, secret_name: str) -> str:
        """Load secret from configured secrets manager."""
        try:
            from multi_eden.build.secrets.factory import get_secrets_manager
            secrets_manager = get_secrets_manager()
            
            logger.debug(f"Loading secret '{secret_name}' from secrets manager")
            response = secrets_manager.get_secret(secret_name, show=True)
            
            if response.meta.success and response.secret:
                return response.secret.value
            else:
                error_msg = response.meta.error.message if response.meta.error else "Unknown error"
                raise ValueError(f"Failed to load secret '{secret_name}': {error_msg}")
                
        except Exception as e:
            raise ValueError(f"Failed to load secret '{secret_name}' from secrets manager: {e}")
    
    def _display_results(self, processed_vars: List[Tuple], failed_vars: List[Tuple], context: Dict[str, Any]):
        """Display the results of environment loading."""
        
        # Configuration source table
        print("\n" + "=" * 50, file=sys.stderr)
        print("🔧 CONFIGURATION SOURCE", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        
        test_mode = context.get('test_mode')
        env_name = context.get('env_name')
        task_name = context.get('task_name')
        
        if test_mode:
            print(f"Test Suite: {test_mode}", file=sys.stderr)
            print(f"  └─ As per: invoke test <suite>", file=sys.stderr)
            print(f"  └─ Source: tests.yaml", file=sys.stderr)
        
        if task_name:
            print(f"Task: {task_name}", file=sys.stderr)
            print(f"  └─ Source: tasks.yaml", file=sys.stderr)
        
        if env_name:
            print(f"Config Environment: {env_name}", file=sys.stderr)
        else:
            print("Config Environment: (none)", file=sys.stderr)
        
        print("=" * 50, file=sys.stderr)
        
        # Environment variables table
        print("\n" + "=" * 76, file=sys.stderr)
        print("🔧 ENVIRONMENT VARIABLES", file=sys.stderr)
        print("=" * 76, file=sys.stderr)
        
        # Sort variables by name for consistent display
        processed_vars.sort(key=lambda x: x[0])
        
        # Combine all variables for sorted display
        all_vars = []
        
        # Add successful variables
        for name, value, source in processed_vars:
            # Limit value to 24 chars max to ensure space before SOURCE column
            if len(value) > 24:
                display_value = value[:21] + "..."
            else:
                display_value = value
            all_vars.append((name, "✅", display_value, source))
        
        # Add failed variables
        for name, error in failed_vars:
            all_vars.append((name, "❌", "(error)", "unknown"))
        
        # Show column headers and rows only if there are variables
        if all_vars:
            print(f"{'VARIABLE':<25} {'VALUE':<25} {'SOURCE':<25}", file=sys.stderr)
            print("-" * 76, file=sys.stderr)
            
            # Sort all variables by name and display
            all_vars.sort(key=lambda x: x[0])
            for name, status, value, source in all_vars:
                print(f"{status} {name:<23} {value:<24} {source:<25}", file=sys.stderr)
        
        print("=" * 76, file=sys.stderr)


# Global loader instance
_loader = None

def get_dynamic_loader() -> DynamicEnvironmentLoader:
    """Get the global dynamic loader instance."""
    global _loader
    if _loader is None:
        _loader = DynamicEnvironmentLoader()
    return _loader

def load_env(env_name: Optional[str] = None,
             test_mode: Optional[str] = None,
             task_name: Optional[str] = None,
             dynamics: Optional[Dict[str, Callable]] = None,
             quiet: bool = False) -> Dict[str, Tuple[str, str]]:
    """
    Dynamic environment loading function using loading.yaml configuration.
    
    Loads environment variables from multiple sources with defined precedence.
    """
    loader = get_dynamic_loader()
    return loader.load_environment(
        env_name=env_name,
        test_mode=test_mode,
        task_name=task_name,
        dynamics=dynamics,
        quiet=quiet
    )


def _get_app_config() -> Optional[Dict[str, Any]]:
    """Get application configuration from app.yaml."""
    from pathlib import Path
    import yaml
    
    app_yaml_path = Path.cwd() / "config" / "app.yaml"
    if not app_yaml_path.exists():
        return None
    
    try:
        with open(app_yaml_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None
