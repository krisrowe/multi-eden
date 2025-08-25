"""
Generic data models for AI services.
"""

from typing import Generic, TypeVar, Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field

# Generic type for items in ModelBasedServiceResponse
T = TypeVar('T')

class ModelBasedServiceResponse(BaseModel, Generic[T]):
    """Structured response from model-based services with metadata."""
    meta: Dict[str, Union[str, float]] = Field(description="Service metadata including provider, model, and timing")
    items: List[T] = Field(description="Service-specific items")
    status: str = Field(description="Service status")

    @classmethod
    def create(cls, provider: str, model: str, items: List[T], status: str = "success", time: Optional[float] = None) -> 'ModelBasedServiceResponse[T]':
        """Create a ModelBasedServiceResponse with the given metadata."""
        meta = {
            "provider": provider,
            "model": model
        }
        if time is not None:
            meta["time"] = time

        return cls(
            meta=meta,
            items=items,
            status=status
        )
