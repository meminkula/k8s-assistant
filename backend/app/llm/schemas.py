from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class IntentType(str, Enum):
    LIST_PODS = "list_pods"
    LIST_DEPLOYMENTS = "list_deployments"
    GET_LOGS = "get_logs"

class ParsedIntent(BaseModel):
    intent: IntentType
    namespace: str = Field(default="default")
    resource_name: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)