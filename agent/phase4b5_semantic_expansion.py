"""Phase 4B.5: semantic catalog audit and candidate gating (no database writes).

Existing catalogs remain untouched. This module does not authorize SQL execution.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDENT = re.compile(r"[a-z_][a-z_0-9]*")
FUNC = {"sum", "avg", "count", "distinct", "nullif", "coalesce", "case", "when", "then", "else", "end", "as", "and", "or", "filter", "where", "true", "false"}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def formula_references(formula):
    """Conservative identifier extraction for current simple catalog expressions.

    Formula syntax beyond supported aggregates is flagged for manual review.
    """
    if not isinstance(formula, str) or not formula.strip():
        return set(), ["empty_formula"]
    if not re.fullmatch(r"[A-Za-z_0-9\s(),.+*/%<>=!-]+", formula):
        return set(), ["unsupported_formula_syntax"]
    names = set(IDENT.findall(formula.lower())) - FUNC
    return names, []


def audit_catalog(catalog, live_audit):
    sources = live_audit.get("sources", {})
    rows = []
    for metric in catalog.get("metrics", []):
        name = metric["metric_name"]
        source = metric["source_view"]
        formula = metric.get("formula", "")
        names, issues = formula_references(formula)
        source_status = sources.get(source)
        if not source_status:
            issues.append("source_missing_from_audit")
        else:
            columns = set(source_status.get("live_columns", []))
            if not source_status.get("columns_verified"):
                issues.append("columns_unverified")
            for column in sorted(names - columns):
                issues.append("unknown_formula_column:" + column)
            date_field = metric.get("time_field")
            if date_field and date_field not in columns:
                issues.append("unknown_time_column:" + date_field)
            grain = source_status.get("checks", {}).get("grain", {}).get("status")
            if grain != "VERIFIED":
                issues.append("grain_unverified:" + str(grain))
        # We do not interpret absence of issues as executable approval. Coverage and measure safety are separate.
        rows.append({"metric": name, "domain": metric.get("domain"), "source": source,
                     "source_contract_status": "NEEDS_REPAIR" if issues else "COLUMN_CHECK_PASSED_NOT_EXECUTION_APPROVED",
                     "issues": issues, "execution_approved": False})
    return rows


def assess_candidates(candidates, live_audit):
    sources = live_audit.get("sources", {})
    results = []
    for candidate in candidates["candidates"]:
        source = candidate["source"]
        columns = set(sources.get(source, {}).get("live_columns", []))
        missing = sorted(set(candidate["required_columns"]) - columns)
        verdict = ("NEEDS_SOURCE_METADATA" if source not in sources else
                   "NEEDS_COLUMN_MAPPING" if missing else "READY_FOR_SEMANTIC_REVIEW")
        results.append({"metric": candidate["metric_id"], "domain": candidate["domain"],
                        "source": source, "status": verdict, "missing_columns": missing,
                        "execution_approved": False,
                        "next_gate": "validate denominators, time basis, data scope, and measure-safe dimensions"})
    return results


def build_report(catalog_path, audit_path, candidate_path):
    catalog = load_json(catalog_path)
    audit = load_json(audit_path)
    candidates = load_json(candidate_path)
    return {"phase": "4B.5", "audit_basis": str(audit_path),
            "disclaimer": "Static contract checks only; no database query or metric automatically approved.",
            "existing_metrics": audit_catalog(catalog, audit),
            "candidate_metrics": assess_candidates(candidates, audit)}
