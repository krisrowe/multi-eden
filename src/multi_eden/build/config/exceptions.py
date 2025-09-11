"""
Exception classes with built-in guidance for environment loading.
"""
import sys


class ConfigException(Exception):
    """Base exception for all configuration errors."""
    def __init__(self, message: str, error_type: str = None, provider: str = None, 
                 secret_name: str = None, env_name: str = None, variable_name: str = None):
        super().__init__(message)
        self.error_type = error_type
        self.provider = provider
        self.secret_name = secret_name
        self.env_name = env_name
        self.variable_name = variable_name
        self.guidance = self._generate_guidance()

    def _get_current_command(self):
        """Get the current command being executed."""
        if len(sys.argv) > 0:
            # Get the full command with all arguments, but use just the filename for the executable
            executable = sys.argv[0].split('/')[-1]  # Get just the filename, not full path
            args = sys.argv[1:]  # Get all arguments
            if args:
                return f"{executable} {' '.join(args)}"
            else:
                return executable
        return "unknown command"

    def _generate_guidance(self):
        """Override in subclasses to provide specific guidance."""
        return f"""
❌ Configuration error: {self}
💡 Check your configuration and try again
"""


class ProjectIdRequiredException(ConfigException):
    """Raised when PROJECT_ID is required for Google Cloud services but not available."""
    def __init__(self, message: str, service_type: str = None, **kwargs):
        super().__init__(message, **kwargs)
        self.service_type = service_type

    def _generate_guidance(self):
        command = self._get_current_command()
        return f"""
❌ Project ID required for Google Cloud services
💡 Resolve this in one of the following ways:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify an environment: {command} --dproj=<your-environment>
"""


class NoProjectIdForGoogleSecretsException(ConfigException):
    """Raised when Google Secret Manager is configured but PROJECT_ID is missing."""
    def __init__(self, message: str, secret_name: str, **kwargs):
        super().__init__(message, secret_name=secret_name, **kwargs)

    def _generate_guidance(self):
        command = self._get_current_command()
        return f"""
❌ Secret '{self.secret_name}' unavailable because Google Secret Manager is used per app.yaml and no PROJECT_ID is available
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Specify an environment: {command} --dproj=dev
      (Note: --dproj must be a name found in .projects file that is mapped to a Google Cloud project id
       where {self.secret_name} is registered as the name of a secret in Secrets Manager)
   2. Or set PROJECT_ID environment variable: export PROJECT_ID=your-project
"""


class NoKeyCachedForLocalSecretsException(ConfigException):
    """Raised when local secrets are configured but no key is cached for decryption."""
    def __init__(self, message: str, secret_name: str, **kwargs):
        super().__init__(message, secret_name=secret_name, **kwargs)

    def _generate_guidance(self):
        return f"""
❌ Secret '{self.secret_name}' unavailable because local secrets require a cached decryption key but none is available
💡 You're configured for local secrets manager in app.yaml, therefore, you must do the following:
   1. Set the cached key: invoke secrets.set-cached-key --passphrase="your-passphrase"
   2. Validate the secret is accessible: invoke secrets.get {self.secret_name}
"""


class LocalSecretNotFoundException(ConfigException):
    """Raised when local secrets are accessible but the specific secret is not found."""
    def __init__(self, message: str, secret_name: str, **kwargs):
        super().__init__(message, secret_name=secret_name, **kwargs)

    def _generate_guidance(self):
        return f"""
❌ Secret '{self.secret_name}' not found in local secrets file
💡 You're configured for local secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets.set {self.secret_name} "your-value"
   2. Or check if secret exists: invoke secrets.list
"""


class GoogleSecretNotFoundException(ConfigException):
    """Raised when Google Secret Manager is accessible but the specific secret is not found."""
    def __init__(self, message: str, secret_name: str, env_name: str = None, **kwargs):
        super().__init__(message, secret_name=secret_name, env_name=env_name, **kwargs)

    def _generate_guidance(self):
        command = self._get_current_command()
        env_name = self.env_name or '<your-environment>'
        return f"""
❌ Secret '{self.secret_name}' not found in Google Secret Manager
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets.set {self.secret_name} --dproj={env_name}
   2. Or check if secret exists: invoke secrets.list --dproj={env_name}
      (Note: --dproj must be a name found in .projects file that is mapped to a Google Cloud project id
       where {self.secret_name} is registered as the name of a secret in Secrets Manager)
"""


# Legacy exceptions for backward compatibility (will be removed)
class ProjectIdNotFoundException(ConfigException):
    """Legacy: Use ProjectIdRequiredException instead."""
    def __init__(self, message: str, env_name: str = None, var_name: str = None, 
                 configured_layer: str = None, projects_file_exists: bool = False):
        super().__init__(message, env_name=env_name, variable_name=var_name)
        self.configured_layer = configured_layer
        self.projects_file_exists = projects_file_exists


class ProjectsFileNotFoundException(ConfigException):
    """Legacy: Use ProjectIdRequiredException instead."""
    def __init__(self, message: str, env_name: str = None, var_name: str = None,
                 configured_layer: str = None):
        super().__init__(message, env_name=env_name, variable_name=var_name)
        self.configured_layer = configured_layer
        self.projects_file_exists = False


class SecretUnavailableException(ConfigException):
    """Legacy: Use specific secret exceptions instead."""
    def __init__(self, message: str, secret_name: str = None, var_name: str = None,
                 configured_layer: str = None):
        super().__init__(message, secret_name=secret_name, variable_name=var_name)
        self.configured_layer = configured_layer


class EnvironmentLoadError(ConfigException):
    """Legacy: Use specific config exceptions instead."""
    pass


class EnvironmentNotFoundError(ConfigException):
    """Legacy: Use specific config exceptions instead."""
    pass


class EnvironmentCorruptionError(ConfigException):
    """Raised when environment variables have been corrupted since last load."""
    def __init__(self, message: str, corrupted_vars: list = None):
        self.corrupted_vars = corrupted_vars or []
        super().__init__(message, error_type="environment_corruption")
    
    def _generate_guidance(self):
        """Generate specific guidance for environment corruption."""
        return f"""
❌ Environment corruption detected: {self}

The environment variables have been modified outside of the load_env system
since the last successful load. This can cause inconsistent behavior.

Corrupted variables: {', '.join(self.corrupted_vars) if self.corrupted_vars else 'Unknown'}

To fix this:
1. Clear the environment: clear_env()
2. Reload your environment: load_env(params)
3. Avoid manually modifying environment variables that are managed by load_env

If you need to modify environment variables, do it through the configuration
system rather than directly modifying os.environ.
"""


class RemoteApiTestingException(ConfigException):
    """Raised when remote API testing configuration is invalid."""
    def __init__(self, message: str, missing_vars: list = None, profile_name: str = None):
        self.missing_vars = missing_vars or []
        self.profile_name = profile_name
        super().__init__(message, error_type="remote_api_testing")
    
    def _generate_guidance(self):
        """Generate specific guidance for remote API testing configuration."""
        command = self._get_current_command()
        return f"""
❌ Remote API testing configuration error: {self}

This error occurs because TEST_API_MODE=REMOTE is set in profile '{self.profile_name or 'Unknown'}', 
but the required configuration variables are missing to build the API URL.

Missing variables: {', '.join(self.missing_vars) if self.missing_vars else 'Unknown'}

💡 Resolve this in one of the following ways (option 1 is strongly preferred):

1. Use built-in deployment profiles (STRONGLY PREFERRED):
   {command} --target local     # Uses LOCAL=true + PORT=8000
   {command} --target dev       # Uses PROJECT_ID + APP_ID from dev profile
   {command} --target prod      # Uses PROJECT_ID + APP_ID from prod profile
   
   The --target option automatically provides the same variable combination 
   that you would set manually in option 2 below.

2. Set environment variables directly:
   For local testing: export LOCAL=true && export PORT=8000
     → Builds: http://localhost:8000
   
   For cloud testing: export PROJECT_ID=your-project && export APP_ID=your-app-id
     → Uses PROJECT_ID to find the Google Cloud project
     → Uses APP_ID to find the Cloud Run service by name (e.g., "your-app-id")
     → Retrieves the service URL (e.g., https://your-app-id-xyz123-uc.a.run.app)

3. Use explicit URL: export TEST_API_URL=https://your-api.com

4. Override configuration in your app's config.yaml:
   Add the missing variables to the {self.profile_name or 'target'} profile
   (This is the least recommended approach)
"""

