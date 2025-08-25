# multi-eden SDK

This SDK provides a set of reusable components for building AI-powered applications with easy management of environment configuration.

## Configuration

The SDK is designed to work with minimal configuration, using sensible defaults that can be easily overridden by the application.

### Test Configuration (`tests.yaml`)

The SDK's test runner (`invoke test`) is configured using a `tests.yaml` file. The SDK provides a default version of this file, which is located at `multi_env_sdk/config/defaults/tests.yaml`.

Applications can override this default configuration by creating their own `tests.yaml` file in the root of the project directory. When the test runner is invoked, it will look for a `tests.yaml` file in the project root first. If found, it will be used; otherwise, the SDK's default configuration will be used.