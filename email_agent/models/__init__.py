"""Email agent models package"""

from .email_models import (
    EmailData,
    ExtractedData, 
    ValidationError,
    ActionPlan,
    AgentState
)

__all__ = [
    "EmailData",
    "ExtractedData", 
    "ValidationError",
    "ActionPlan",
    "AgentState"
]
