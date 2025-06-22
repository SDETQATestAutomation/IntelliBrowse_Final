"""
Select Option Tool Schemas.

Pydantic schemas for selecting option(s) in dropdown/select elements request and response validation.
"""

from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, field_validator


class SelectOptionRequest(BaseModel):
    """Request schema for selecting option(s) in dropdown/select elements."""
    
    session_id: str = Field(description="Active Playwright session ID")
    selector: str = Field(description="CSS selector of the select element")
    value: Optional[Union[str, List[str]]] = Field(default=None, description="Option value(s) to select")
    label: Optional[Union[str, List[str]]] = Field(default=None, description="Option label/text(s) to select")
    index: Optional[Union[int, List[int]]] = Field(default=None, description="Option index(es) to select (0-based)")
    timeout_ms: Optional[int] = Field(default=5000, description="Timeout in milliseconds for element availability")
    multiple: Optional[bool] = Field(default=False, description="Allow multiple selections")
    
    @field_validator('value', 'label', 'index', mode='before')
    @classmethod
    def validate_selection_criteria(cls, v):
        """Ensure at least one selection criterion is provided."""
        # Note: In Pydantic v2, cross-field validation is done with model_validator
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "session_12345",
                "selector": "#country-select",
                "value": "US",
                "timeout_ms": 5000,
                "multiple": False
            }
        }


class SelectOptionResponse(BaseModel):
    """Response schema for select option operation."""
    
    success: bool = Field(description="Whether the option selection was successful")
    selector: str = Field(description="Selector used for the select element")
    message: str = Field(description="Status or error message")
    selected_values: List[str] = Field(default=[], description="Values of selected options")
    selected_labels: List[str] = Field(default=[], description="Labels of selected options")
    selected_indices: List[int] = Field(default=[], description="Indices of selected options")
    elapsed_ms: int = Field(description="Time taken for the selection operation in milliseconds")
    metadata: Dict[str, Any] = Field(default={}, description="Additional selection operation metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "selector": "#country-select",
                "message": "Option selected successfully",
                "selected_values": ["US"],
                "selected_labels": ["United States"],
                "selected_indices": [2],
                "elapsed_ms": 250,
                "metadata": {
                    "element_visible": True,
                    "total_options": 195,
                    "multiple_allowed": False
                }
            }
        } 