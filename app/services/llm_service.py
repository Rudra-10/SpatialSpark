# Re-export for PLAN.md compliance; all logic lives in reasoning_service.py
from app.services.reasoning_service import SpatialReasoningService as LLMService

__all__ = ["LLMService"]

