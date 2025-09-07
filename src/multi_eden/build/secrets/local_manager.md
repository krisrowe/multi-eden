# LocalSecretsManager Behavior Specification

This document defines the expected behavior of `LocalSecretsManager` in all scenarios, including file existence, cached key availability, and operation types.

## Response Modes

The LocalSecretsManager supports two response modes:

- **`throw_not_found=False` (default)**: Returns JSON error responses with structured error information
- **`throw_not_found=True`**: Throws specific exception classes with built-in guidance

**Note**: Only `get_secret` supports the `throw_not_found` parameter because it's the only method used by the environment loading system (`secrets.py`). Other operations always return JSON responses.

All scenarios below show both behaviors in the Response column.

## Scenarios Overview

The behavior depends on three factors:
1. **Secrets file existence** (`~/.secrets` or `LOCAL_SECRETS_REPO` path)
2. **Cached key availability** (passphrase for decryption)
3. **Operation type** (read, write, list, clear)

## Operation Types

- **Read operations**: `get_secret`, `delete_secret` - require decryption (use `@loads_secrets` decorator)
- **Write operations**: `set_secret` - require encryption (cached key) (use `@loads_secrets` decorator)
- **List operations**: `list_secrets` - may or may not require decryption (use `@loads_secrets` decorator)
- **Clear operations**: `clear_all_secrets`, `clear_cached_key` - no decryption needed (NO decorator)

## Scenario Matrix

### Scenario 1: No Secrets File + No Cached Key

| Operation | Behavior | Response |
|-----------|----------|----------|
| `get_secret` | Return error (JSON) or throw exception | `{"meta": {"success": false, "provider": "local", "error": {"code": "SECRET_NOT_FOUND", "message": "No local secrets file found. Use 'invoke secrets.set' to create secrets."}}, "secret": null}`<br><br>or<br><br>`LocalSecretNotFoundException` |
| `set_secret` | Validate key first, then return error | `{"meta": {"success": false, "provider": "local", "error": {"code": "KEY_NOT_SET", "message": "Local secrets require a cached decryption key but none is available"}}, "secret": null}` |
| `list_secrets` | Return empty list | `{"meta": {"success": true, "provider": "local"}, "manifest": {"secrets": []}}` |
| `delete_secret` | Return error | `{"meta": {"success": false, "provider": "local", "operation": "delete", "error": {"code": "SECRET_NOT_FOUND", "message": "No local secrets file found. Use 'invoke secrets.set' to create secrets."}}, "secret_name": "secret-name"}` |
| `clear_all_secrets` | Return success (nothing to clear) | `{"meta": {"success": true, "provider": "local", "operation": "clear"}, "cleared_count": 0, "message": "Successfully cleared 0 secrets"}` |
| `clear_cached_key` | Return success (nothing to clear) | `{"meta": {"success": true, "provider": "local", "operation": "clear_cached_key"}, "key": null}` |

### Scenario 2: No Secrets File + Has Cached Key

| Operation | Behavior | Response |
|-----------|----------|----------|
| `get_secret` | Return error (JSON) or throw exception | `{"meta": {"success": false, "provider": "local", "error": {"code": "SECRET_NOT_FOUND", "message": "No local secrets file found. Use 'invoke secrets.set' to create secrets."}}, "secret": null}`<br><br>or<br><br>`LocalSecretNotFoundException` |
| `set_secret` | Create new file with encrypted secret | `{"meta": {"success": true, "provider": "local", "operation": "set"}, "secret": {"name": "secret-name", "value": null}}` |
| `list_secrets` | Return empty list | `{"meta": {"success": true, "provider": "local"}, "manifest": {"secrets": []}}` |
| `delete_secret` | Return error | `{"meta": {"success": false, "provider": "local", "operation": "delete", "error": {"code": "SECRET_NOT_FOUND", "message": "No local secrets file found. Use 'invoke secrets.set' to create secrets."}}, "secret_name": "secret-name"}` |
| `clear_all_secrets` | Return success (nothing to clear) | `{"meta": {"success": true, "provider": "local", "operation": "clear"}, "cleared_count": 0, "message": "Successfully cleared 0 secrets"}` |
| `clear_cached_key` | Clear cached key | `{"meta": {"success": true, "provider": "local", "operation": "clear_cached_key"}, "key": null}` |

### Scenario 3: Has Secrets File + No Cached Key

| Operation | Behavior | Response |
|-----------|----------|----------|
| `get_secret` | Return error (JSON) or throw exception | `{"meta": {"success": false, "provider": "local", "error": {"code": "KEY_NOT_SET", "message": "Local secrets require a cached decryption key but none is available"}}, "secret": null}`<br><br>or<br><br>`NoKeyCachedForLocalSecretsException` |
| `set_secret` | Return error | `{"meta": {"success": **false**, "provider": "local", "error": {"code": "KEY_NOT_SET", "message": "Local secrets require a cached decryption key but none is available"}}, "secret": null}` |
| `list_secrets` | Return error | `{"meta": {"success": **false**, "provider": "local", "error": {"code": "KEY_NOT_SET", "message": "Local secrets require a cached decryption key but none is available"}}, "manifest": null}` |
| `delete_secret` | Return error | `{"meta": {"success": **false**, "provider": "local", "operation": "delete", "error": {"code": "KEY_NOT_SET", "message": "Local secrets require a cached decryption key but none is available"}}, "secret_name": "secret-name"}` |
| `clear_all_secrets` | Retrieve secrets, delete secrets file, return count | `{"meta": {"success": true, "provider": "local", "operation": "clear"}, "cleared_count": N, "message": "Successfully cleared N secrets"}` |
| `clear_cached_key` | Clear cached key | `{"meta": {"success": true, "provider": "local", "operation": "clear_cached_key"}, "key": null}` |

### Scenario 4: Has Secrets File + Has Cached Key

| Operation | Behavior | Response |
|-----------|----------|----------|
| `get_secret` | Decrypt and return secret | `{"meta": {"success": true, "provider": "local"}, "secret": {"name": "secret-name", "value": "secret-value"}}` |
| `set_secret` | Encrypt and store secret | `{"meta": {"success": true, "provider": "local", "operation": "set"}, "secret": {"name": "secret-name", "value": null}}` |
| `list_secrets` | Decrypt and return all secrets | `{"meta": {"success": true, "provider": "local"}, "manifest": {"secrets": [{"name": "secret1"}, {"name": "secret2"}]}}` |
| `delete_secret` | Decrypt, remove secret, save | `{"meta": {"success": true, "provider": "local", "operation": "delete"}, "secret_name": "secret-name"}` |
| `clear_all_secrets` | Retrieve secrets, delete secrets file, return count | `{"meta": {"success": true, "provider": "local", "operation": "clear"}, "cleared_count": N, "message": "Successfully cleared N secrets"}` |
| `clear_cached_key` | Clear cached key | `{"meta": {"success": true, "provider": "local", "operation": "clear_cached_key"}, "key": null}` |

### Scenario 5: Has Secrets File + Has Cached Key + Secret Name Not Found

| Operation | Behavior | Response |
|-----------|----------|----------|
| `get_secret` | Return error (JSON) or throw exception | `{"meta": {"success": false, "provider": "local", "error": {"code": "SECRET_NOT_FOUND", "message": "Secret 'secret-name' not found"}}, "secret": null}`<br><br>or<br><br>`LocalSecretNotFoundException` |
| `set_secret` | Add new secret to file | `{"meta": {"success": true, "provider": "local", "operation": "set"}, "secret": {"name": "secret-name", "value": null}}` |
| `list_secrets` | Return all existing secrets | `{"meta": {"success": true, "provider": "local"}, "manifest": {"secrets": [{"name": "secret1"}, {"name": "secret2"}]}}` |
| `delete_secret` | Return error for missing secret | `{"meta": {"success": false, "provider": "local", "operation": "delete", "error": {"code": "SECRET_NOT_FOUND", "message": "Secret 'secret-name' not found"}}, "secret_name": "secret-name"}` |
| `clear_all_secrets` | Retrieve secrets, delete secrets file, return count | `{"meta": {"success": true, "provider": "local", "operation": "clear"}, "cleared_count": N, "message": "Successfully cleared N secrets"}` |
| `clear_cached_key` | Clear cached key | `{"meta": {"success": true, "provider": "local", "operation": "clear_cached_key"}, "key": null}` |

## Exception Types and Guidance for Environment Variable Loading

**Note**: Exceptions are only thrown by `get_secret` when `throw_not_found=True` (used by the environment variable loading system). Other operations always return JSON responses.

### LocalSecretNotFoundException
**When**: `get_secret` when no secrets file exists, or when secret name not found in existing file
**Thrown by**: `get_secret` in Scenarios 1, 2, and 5
**Guidance**: 
```
❌ Secret 'gemini-api-key' not found in local secrets file
💡 You're configured for local secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets.set gemini-api-key "your-value"
   2. Or check if secret exists: invoke secrets.list
```

### NoKeyCachedForLocalSecretsException
**When**: `get_secret` when secrets file exists but no cached key, or when no file exists but operation requires key
**Thrown by**: `get_secret` in Scenarios 1 and 3
**Guidance**:
```
❌ Secret 'gemini-api-key' unavailable because local secrets require a cached decryption key but none is available
💡 You're configured for local secrets manager in app.yaml, therefore, you must do the following:
   1. Set the cached key: invoke secrets.set-cached-key --passphrase="your-passphrase"
   2. Validate the secret is accessible: invoke secrets.get gemini-api-key
```

## Success Response Examples

### get_secret (success)
```json
{
  "meta": {
    "success": true,
    "provider": "local"
  },
  "secret": {
    "name": "gemini-api-key",
    "value": "sk-1234567890abcdef"
  }
}
```

### set_secret (success)
```json
{
  "meta": {
    "success": true,
    "provider": "local",
    "operation": "set"
  },
  "secret": {
    "name": "gemini-api-key",
    "value": null
  }
}
```

### list_secrets (success)
```json
{
  "meta": {
    "success": true,
    "provider": "local"
  },
  "manifest": {
    "secrets": [
      {
        "name": "gemini-api-key"
      },
      {
        "name": "jwt-secret-key"
      }
    ]
  }
}
```

### clear_all_secrets (success)
```json
{
  "meta": {
    "success": true,
    "provider": "local",
    "operation": "clear"
  },
  "cleared_count": 2,
  "message": "Successfully cleared 2 secrets"
}
```

### clear_cached_key (success)
```json
{
  "meta": {
    "success": true,
    "provider": "local",
    "operation": "clear_cached_key"
  },
  "key": null
}
```

## Error Response Examples

### SECRET_NOT_FOUND
**When**: `get_secret` when no secrets file exists, or `delete_secret` when no file exists or secret not found
**Scenarios**: 1, 2, 5
```json
{
  "meta": {
    "success": false,
    "provider": "local",
    "error": {
      "code": "SECRET_NOT_FOUND",
      "message": "No local secrets file found. Use 'invoke secrets.set' to create secrets."
    }
  },
  "secret": null
}
```

### KEY_NOT_SET
**When**: Any operation when secrets file exists but no cached key, or when no file exists but operation requires key
**Scenarios**: 1 (set_secret), 3 (all operations)
```json
{
  "meta": {
    "success": false,
    "provider": "local",
    "error": {
      "code": "KEY_NOT_SET",
      "message": "Local secrets require a cached decryption key but none is available"
    }
  },
  "secret": null
}
```

## Key Design Principles

1. **Clear operations are always safe**: `clear_all_secrets` and `clear_cached_key` never require cached keys and don't use the `@loads_secrets` decorator
2. **Write operations always need encryption**: `set_secret` requires cached key even for new files
3. **Read operations need decryption**: All read operations require cached key when file exists
4. **List operations are permissive**: `list_secrets` returns empty list when no file exists
5. **Exceptions carry context**: All exceptions include secret name and actionable guidance
6. **Consistent response format**: All responses follow the same JSON structure
7. **Decorator usage**: Only operations that need to load/decrypt secrets use the `@loads_secrets` decorator
