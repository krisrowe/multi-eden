"""
Test data helper utilities for loading test files and constructing paths.
"""
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Union, List


def get_unit_test_data_folder_path(operation: str, interface_type: str) -> Path:
    """
    Get the folder path for unit test data.
    
    Args:
        operation: The operation type (e.g., 'meal-analysis', 'meal-segmentation')
        interface_type: The interface type (e.g., 'llm', 'service')
    
    Returns:
        Path to the test data folder
    """
    # Use current working directory to locate test data
    # This makes the SDK more robust when imported from different contexts
    repo_root = Path.cwd()
    # Map interface_type to directory name
    dir_name = f"{interface_type}-output"
    return repo_root / 'test-data' / 'unit' / operation / dir_name


def get_unit_test_case_data(operation: str, interface_type: str, test_case_id: str) -> Dict[str, Any]:
    """
    Load unit test case data from a file.
    
    Args:
        operation: The operation type (e.g., 'meal-analysis', 'meal-segmentation')
        interface_type: The interface type (e.g., 'llm', 'service')
        test_case_id: The test case identifier (e.g., 'single-item-n-std-units')
    
    Returns:
        Loaded JSON data from the test file
    
    Raises:
        FileNotFoundError: If the test file doesn't exist
    """
    folder_path = get_unit_test_data_folder_path(operation, interface_type)
    file_path = folder_path / f"{test_case_id}.json"
    
    if not file_path.exists():
        raise FileNotFoundError(f"Test file not found: {file_path}")
    
    with open(file_path, 'r') as f:
        return json.load(f)


def get_prompt_for_case(test_case_id: str, data_path: str) -> str:
    """
    Retrieve the prompt text for a given test case ID from a cases.yaml file.
    
    Args:
        test_case_id: The ID of the test case (e.g., "single-item-n-std-units")
        data_path: Path to the test data directory containing cases.yaml
        
    Returns:
        The prompt text for the test case
        
    Raises:
        FileNotFoundError: If cases.yaml doesn't exist
        KeyError: If the test case ID is not found
        yaml.YAMLError: If cases.yaml is malformed
    """
    cases_file = Path(data_path) / "cases.yaml"
    
    if not cases_file.exists():
        raise FileNotFoundError(f"cases.yaml not found at {cases_file}")
    
    with open(cases_file, 'r') as f:
        cases_data = yaml.safe_load(f)
    
    if 'cases' not in cases_data:
        raise KeyError("No 'cases' section found in cases.yaml")
    
    for case in cases_data['cases']:
        if case.get('id') == test_case_id:
            return case['prompt']
    
    raise KeyError(f"Test case ID '{test_case_id}' not found in cases.yaml")


def get_operation(cls) -> str:
    """
    Extract the operation name from a class.
    
    Args:
        cls: The class to inspect
        
    Returns:
        The operation name
        
    Raises:
        AttributeError: If the class doesn't have an operation property/class-var
    """
    if hasattr(cls, 'operation'):
        return cls.operation
    else:
        raise AttributeError(f"Class {cls.__name__} does not have an 'operation' attribute")


def get_interface_type(cls) -> str:
    """
    Determine the interface type based on class inheritance.
    
    Args:
        cls: The class to inspect
        
    Returns:
        'llm' if the class inherits from ModelClient, 'service' if it inherits from ModelBasedService
        
    Raises:
        ValueError: If the class doesn't inherit from either ModelClient or ModelBasedService
    """
    # Import here to avoid circular imports
    try:
        from .base_client import ModelClient
        from .services import ModelBasedService
        
        # Check inheritance hierarchy and use class attributes
        if issubclass(cls, ModelClient):
            return ModelClient.interface_type
        elif issubclass(cls, ModelBasedService):
            return ModelBasedService.interface_type
        else:
            raise ValueError(f"Class {cls.__name__} must inherit from either ModelClient or ModelBasedService")
    except ImportError as e:
        raise ImportError(f"Failed to import required base classes: {e}")


def get_testable_prompt(operation: str, interface_type: str, test_case_id: str) -> str:
    """
    Get prompt for a specific operation, interface type, and test case.
    
    Args:
        operation: The operation type (e.g., "meal-analysis", "meal-segmentation")
        interface_type: The interface type ("llm" or "service")
        test_case_id: The ID of the test case
        
    Returns:
        The prompt text for the test case
        
    Example:
        get_testable_prompt("meal-analysis", "llm", "single-item-n-std-units")
        get_testable_prompt("meal-segmentation", "service", "multi-item-meal")
    """
    # Use current working directory to locate test data
    data_path = Path.cwd() / "test-data" / "unit" / operation / f"{interface_type}-output"
    return get_prompt_for_case(test_case_id, str(data_path))


def get_test_case_ids(operation: str, interface_type: str) -> List[str]:
    """
    Get all test case IDs for a given operation and interface type.
    
    Args:
        operation: The operation type (e.g., "meal-analysis", "meal-segmentation")
        interface_type: The interface type ("llm" or "service")
        
    Returns:
        List of test case IDs
        
    Raises:
        FileNotFoundError: If cases.yaml doesn't exist
        yaml.YAMLError: If cases.yaml is malformed
    """
    data_path = Path.cwd() / "test-data" / "unit" / operation / f"{interface_type}-output"
    cases_file = data_path / "cases.yaml"
    
    if not cases_file.exists():
        raise FileNotFoundError(f"cases.yaml not found at {cases_file}")
    
    with open(cases_file, 'r') as f:
        cases_data = yaml.safe_load(f)
    
    if 'cases' not in cases_data:
        raise KeyError("No 'cases' section found in cases.yaml")
    
    return [case.get('id') for case in cases_data['cases'] if case.get('id')]


