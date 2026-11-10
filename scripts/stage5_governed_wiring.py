"""AST-based checks for existing governed CLI wiring.

Validation-only code. Does not execute investigation functions.
"""
import ast
from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parent / "phase5_1_playground.py"
).read_text(encoding="utf-8-sig")

TREE = ast.parse(SOURCE)


def _name(node):
    return node.id if isinstance(node, ast.Name) else None


def _calls(name):
    return [
        node for node in ast.walk(TREE)
        if isinstance(node, ast.Call)
        and _name(node.func) == name
    ]


def router_verified():
    calls = _calls("multi_domain_route")

    return len(calls) == 2 and all(
        len(c.args) == 4
        and _name(c.args[0]) in ("q", "question")
        and [_name(a) for a in c.args[1:]] == [
            "existing_dispatch",
            "finance_reader",
            "existing_finance_investigator",
        ]
        and len(c.keywords) == 1
        and c.keywords[0].arg == "cohort_audit"
        for c in calls
    )


def repair_verified():
    calls = _calls("repair_incident")

    return len(calls) == 3 and all(
        len(c.args) == 4
        and _name(c.args[0]) in ("q", "question")
        and [_name(a) for a in c.args[1:]] == [
            "response",
            "existing_finance_investigator",
            "finance_reader",
        ]
        and not c.keywords
        for c in calls
    )


def compiled_finance_verified():
    calls = _calls("adaptive_investigation")

    return any(
        any(
            isinstance(node, ast.Call)
            and _name(node.func) == "CompiledComparisonInterpreter"
            for argument in call.args
            for node in ast.walk(argument)
        )
        for call in calls
    )
