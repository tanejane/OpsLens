from __future__ import annotations
import re
import calendar
from datetime import date

class InvestigationUnavailable(RuntimeError):
    pass

def month_window(text: str) -> tuple[str, str]:
    m = re.search(r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(20\d{2})\b", text, re.I)
    if not m:
        raise InvestigationUnavailable("Explicit month and year needed, e.g. 'June 2018'. No date guessed.")
    month = list(calendar.month_name).index(m.group(1).capitalize())
    year = int(m.group(2))
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


def previous_month(start: str) -> str:
    d = date.fromisoformat(start)
    return date(d.year - (d.month == 1), (d.month - 2) % 12 + 1, 1).isoformat()


def require_identifiers(cols: list[str], names: set[str], relation: str):
    missing = sorted(names.difference(set(cols)))
    if missing:
        raise InvestigationUnavailable(f"{relation} missing required columns: {missing}")

def num(value, default=0.0):
    """Safely convert database numeric values to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default