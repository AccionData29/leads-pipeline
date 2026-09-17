from dataclasses import dataclass
from datetime import datetime
from typing import Any

@dataclass
class LeadEnrichment:
    lead_id: str
    model_interest: str | None = None
    initial_payment: float | None = None
    payment_method: str | None = None
    intent: str | None = None
    main_objection: str | None = None
    requested_appointment: bool = False
    requested_quote: bool = False
    confidence: float = 0.0
    provider: str = "mock"
    model_name: str | None = None
    prompt_version: str = "1.0"

@dataclass
class ScoreResult:
    lead_id: str
    score: float
    priority: str
    model_version: str
    reasons: list[str]
    features: dict[str, Any]

@dataclass
class Assignment:
    lead_id: str
    advisor_id: str
    assignment_date: datetime
    priority_at_assignment: str
    position: int
