
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedQuestion:
    intent: str
    primary_metric: str | None
    comparison_metric: str | None
    asks_for_root_cause: bool
    normalized_question: str


REVENUE_TERMS = {
    "revenue", "sales", "gmv", "turnover", "营收", "销售额", "sales went up",
}
PROFIT_TERMS = {
    "profit", "contribution profit", "margin", "利润", "盈利", "profitability",
}
CAUSE_TERMS = {
    "why", "cause", "caused", "reason", "investigate", "root cause",
    "为什么", "原因", "怎么回事",
}


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def parse_question(question: str) -> ParsedQuestion:
    """
    Deterministic NLU baseline.

    This is NOT intended to replace an LLM. It exists so routing, state updates,
    tool choice and stopping behavior can be validated independently from model
    variability.
    """
    normalized = re.sub(r"\s+", " ", question.strip().lower())

    has_revenue = _contains_any(normalized, REVENUE_TERMS)
    has_profit = _contains_any(normalized, PROFIT_TERMS)
    asks_cause = _contains_any(normalized, CAUSE_TERMS)

    intent = (
        "root_cause_investigation"
        if asks_cause or (has_revenue and has_profit)
        else "metric_question"
    )

    primary_metric = "contribution_profit" if has_profit else None
    comparison_metric = "revenue" if has_revenue else None

    return ParsedQuestion(
        intent=intent,
        primary_metric=primary_metric,
        comparison_metric=comparison_metric,
        asks_for_root_cause=asks_cause or (has_revenue and has_profit),
        normalized_question=normalized,
    )
