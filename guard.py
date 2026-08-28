"""
guard.py — the single choke point every Salesforce read passes through.

Four jobs:
  1. block_dml         — reject INSERT/UPDATE/DELETE/UPSERT/MERGE. Reads only.
  2. enforce_as_of      — inject/verify a date filter so no record newer than
                          the backtest as-of date can leak into a packet.
  3. strip_banned_fields — remove free-text/PII fields (Case bodies, comments,
                          subjects...). Only counts/dates/enums pass through.
                          This is the PII rule AND the prompt-injection
                          containment: customer-authored text never reaches
                          a model.
  4. audit_leakage      — post-hoc scan across a run's records; Gate 0. If
                          this finds anything, evaluate.py refuses to print
                          accuracy numbers for that run.

Nothing in this file calls Salesforce. It only guards queries and records
that salesforce_client.py passes through it.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone


class GuardViolation(Exception):
    """Raised when a query or record would violate a guard rule."""


# ---------------------------------------------------------------------------
# 1. DML block
# ---------------------------------------------------------------------------

_DML_PATTERN = re.compile(r"\b(insert|update|delete|upsert|merge)\b", re.IGNORECASE)


def block_dml(soql: str) -> str:
    """Raise GuardViolation if soql contains a write statement. Read-only or bust."""
    if _DML_PATTERN.search(soql):
        raise GuardViolation(f"DML statement blocked by guard: {soql!r}")
    return soql


# ---------------------------------------------------------------------------
# 2. As-of enforcement
# ---------------------------------------------------------------------------


def _normalize_as_of(as_of_date: str) -> str:
    """Accept 'YYYY-MM-DD' or a full ISO timestamp; return a date-only string."""
    return str(as_of_date)[:10]


def enforce_as_of(soql: str, as_of_date: str, date_field: str = "CreatedDate") -> str:
    """
    Inject a `<date_field> <= as_of_date` bound into a SOQL query.

    If the query already has a WHERE clause, AND the bound into it. If not,
    insert a WHERE clause before ORDER BY / GROUP BY / LIMIT, or at the end.
    Blocks DML first — as-of enforcement is meaningless on a write.
    """
    block_dml(soql)
    as_of = _normalize_as_of(as_of_date)
    clause = f"{date_field} <= {as_of}T23:59:59Z"

    where_match = re.search(r"\bWHERE\b", soql, re.IGNORECASE)
    if where_match:
        idx = where_match.end()
        return f"{soql[:idx]} {clause} AND{soql[idx:]}"

    tail_match = re.search(r"\b(ORDER BY|GROUP BY|LIMIT)\b", soql, re.IGNORECASE)
    if tail_match:
        idx = tail_match.start()
        return f"{soql[:idx]}WHERE {clause} {soql[idx:]}"

    return f"{soql.rstrip()} WHERE {clause}"


# ---------------------------------------------------------------------------
# 3. Banned-field stripping (PII / free-text / prompt-injection containment)
# ---------------------------------------------------------------------------

# Substring match on lowercased field name. Deliberately broad: better to
# over-strip a field a specialist didn't need than leak customer-authored text.
_BANNED_SUBSTRINGS = (
    "description",
    "subject",
    "body",
    "comment",
    "note",
    "verbatim",
    "textbody",
    "htmlbody",
)

# Fields that look free-text by substring match but are safe enums/identifiers —
# checked before the substring match so they are never stripped.
_ALLOW_OVERRIDE = {
    "status",  # not currently a false positive, kept for clarity/extension
}


def _is_banned(field_name: str) -> bool:
    lname = field_name.lower()
    if lname in _ALLOW_OVERRIDE:
        return False
    return any(s in lname for s in _BANNED_SUBSTRINGS)


def strip_banned_fields(record: dict) -> tuple[dict, list[str]]:
    """Return (cleaned_record, stripped_field_names). Never mutates the input."""
    cleaned = {}
    stripped = []
    for key, value in record.items():
        if _is_banned(key):
            stripped.append(key)
        else:
            cleaned[key] = value
    return cleaned, stripped


# ---------------------------------------------------------------------------
# 4. Leakage audit (Gate 0)
# ---------------------------------------------------------------------------

# Deliberately excludes CloseDate: on a renewal Opportunity, CloseDate is the
# forward-looking target (the renewal date itself) and is *expected* to sit
# after as_of. Only check fields that record when something was actually
# observed/logged, never a projected/target date, or every open renewal
# Opportunity would trip Gate 0.
DEFAULT_DATE_FIELDS = ("CreatedDate", "LastModifiedDate", "ActivityDate")


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def audit_leakage(records: list[dict], as_of_date: str, date_fields=DEFAULT_DATE_FIELDS) -> list[dict]:
    """
    Scan records for any date field that falls after as_of_date.

    Returns a list of violation dicts: {record_id, field, value, as_of}.
    Empty list = Gate 0 passes. This is a post-hoc safety net on top of
    enforce_as_of, not a replacement for it — a query built without the
    guard, or a field the guard doesn't filter on, would still be caught here.
    """
    as_of_dt = _parse_date(as_of_date)
    if as_of_dt is None:
        raise GuardViolation(f"invalid as_of_date: {as_of_date!r}")

    violations = []
    for record in records:
        for field in date_fields:
            value = record.get(field)
            record_dt = _parse_date(value)
            if record_dt is not None and record_dt > as_of_dt:
                violations.append(
                    {
                        "record_id": record.get("Id"),
                        "field": field,
                        "value": value,
                        "as_of": as_of_date,
                    }
                )
    return violations


# ---------------------------------------------------------------------------
# Single choke point
# ---------------------------------------------------------------------------


def soql_guard(soql: str, as_of_date: str, date_field: str = "CreatedDate") -> str:
    """The one function salesforce_client.py calls before issuing any query."""
    return enforce_as_of(soql, as_of_date, date_field)
