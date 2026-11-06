
from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from typing_extensions import TypedDict


class HypothesisStatus(str, Enum):
    UNTESTED = "UNTESTED"
    TESTING = "TESTING"
    SUPPORTED = "SUPPORTED"
    WEAK = "WEAK"
    REJECTED = "REJECTED"
    CONFLICTING = "CONFLICTING"


class EvidenceStrength(str, Enum):
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class EvidenceItem(TypedDict):
    evidence_id: str
    source_type: Literal["metric", "sql", "document", "tool", "derived"]
    source_ref: str
    claim: str
    value: Any
    supports_hypotheses: list[str]
    contradicts_hypotheses: list[str]
    strength: EvidenceStrength
    limitations: list[str]


class Hypothesis(TypedDict):
    hypothesis_id: str
    statement: str
    status: HypothesisStatus
    rationale: str
    evidence_for: list[str]
    evidence_against: list[str]
    confidence: float
    next_test: str | None


class InvestigationPlanItem(TypedDict):
    step_id: str
    purpose: str
    tool_name: str
    status: Literal["PENDING", "RUNNING", "DONE", "BLOCKED"]
    expected_grain: str
    hypothesis_ids: list[str]


class InvestigationState(TypedDict):
    question: str
    investigation_id: str

    # Business interpretation
    primary_metric: str | None
    comparison_period: str | None
    business_context: dict[str, Any]

    # Planning
    plan: list[InvestigationPlanItem]
    hypotheses: list[Hypothesis]

    # Evidence
    evidence_ledger: list[EvidenceItem]
    conflicts: list[str]
    missing_evidence: list[str]

    # Control
    current_step: int
    step_budget: int
    tool_call_budget: int
    tool_calls_used: int
    stop_reason: str | None

    # Final
    confidence: float
    conclusion: str | None
    recommended_actions: list[str]
