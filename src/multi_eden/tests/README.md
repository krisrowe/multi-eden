# Multi-Environment SDK Tests

This directory contains tests for the multi_env_sdk package.

## Test Types

### Unit Tests
- `test_config.py` - Unit tests for config module functions
- `test_deploy.py` - Unit tests for deploy module functions

These tests use mocks and don't require external dependencies.

### Integration Tests
- `test_config_init.py` - Integration tests for config bucket initialization

These tests require a real GCP project and test all scenarios end-to-end.

## Running Tests

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Unit Tests Only
```bash
pytest tests/test_config.py tests/test_deploy.py -v
```

### Run Integration Tests
Set up a test project and run:
```bash
export TEST_PROJECT_ID=your-test-project-123
pytest tests/test_config_init.py -v
```

### Run All Tests
```bash
# Unit tests only (no GCP required)
pytest tests/ -m "unit" -v

# Integration tests (requires TEST_PROJECT_ID)
export TEST_PROJECT_ID=your-test-project-123
pytest tests/ -m "integration" -v

# All tests
export TEST_PROJECT_ID=your-test-project-123
pytest tests/ -v
```

## Test Scenarios Covered

The integration tests cover these scenarios:

1. **Fresh project, default bucket** - No existing buckets, use `{app_id}-config`
2. **Fresh project, custom bucket** - No existing buckets, use custom name
3. **Existing bucket matches default** - Idempotent behavior
4. **Existing bucket matches custom** - Idempotent behavior with custom names
5. **Conflict: existing vs default** - Multiple apps in same project
6. **Conflict: existing vs custom** - Bucket name mismatch
7. **App.yaml mismatch** - Different app_id in existing app.yaml
8. **Bucket exists, no label** - Add label to unlabeled bucket

## Test Project Requirements

The test project should:
- Have Cloud Storage API enabled
- Have appropriate IAM permissions for bucket creation/deletion
- Be dedicated for testing (tests will create/delete buckets)

## Cleanup

Integration tests automatically clean up test buckets before and after each test.
