"""
stub_model.py — dry-run fake. Delete once you have an ANTHROPIC_API_KEY.

Produces schema-valid canned responses per role (coordinator / commercial /
relationship / synthesis) so `run.py --dry-run` exercises orchestration,
schemas, guard, and brief rendering without a model call.

Two deliberate design choices, both called out in DOCUMENTATION.md:

1. Specialist packets ARE driven by the actual (guarded, mock) records —
   using signals.yaml's thresholds as simple heuristics — so a human can
   still "read the packets by hand" per the recommended order of work, even
   before a real model is wired in.

2. Synthesis is NOT driven by the packets' content: it always returns the
   same score/band (81 / high) regardless of account. This is intentional.
   evaluate.py's Gate 1 (precision@k) is expected to FAIL on stub output —
   a constant score has no discriminative power. That failure is the harness
   proving it actually checks something, not a bug to fix here.
   Citations are still pulled from real packet evidence_refs, so the
   fabrication check (every citation resolves to a real evidence_ref) still
   passes under stub — only the *score* is canned.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_SIGNALS_PATH = Path(__file__).parent / "signals.yaml"


def _load_signals() -> dict:
    with open(_SIGNALS_PATH) as f:
        data = yaml.safe_load(f)
    return {s["name"]: s for s in data["signals"]}


_SIGNALS = _load_signals()


def generate_coordinator(account_id: str) -> dict:
    return {
        "specialists": ["commercial", "relationship"],
        "tool_budget": 8,
        "rationale": "stub coordinator: always dispatches both specialists at the default tool budget",
    }


# --- Commercial heuristics ----------------------------------------------------

def generate_commercial_packet(account_id: str, as_of: str, records: dict[str, list[dict]]) -> dict:
    signals = []
    evidence_refs = []
    gaps = []

    opportunities = records.get("Opportunity", [])
    history = records.get("OpportunityFieldHistory", [])
    contracts = records.get("Contract", [])
    assets = records.get("Asset", [])

    if not opportunities:
        gaps.append("no open renewal Opportunity found for this account as of " + as_of)
    else:
        opp = opportunities[0]
        evidence_refs.append(f"Opportunity/{opp['Id']}")

        # amount_decrease: any Amount field-history entry where new < old, or Amount < Contract ARR
        arr = contracts[0]["ARR__c"] if contracts else None
        amount_drops = [h for h in history if h.get("Field") == "Amount"]
        if amount_drops:
            h = amount_drops[0]
            evidence_refs.append(f"OpportunityFieldHistory/{h['Id']}")
            old, new = float(h["OldValue"]), float(h["NewValue"])
            pct = (old - new) / old * 100 if old else 0
            severity = "high" if pct > 15 else "medium" if pct > 5 else None
            if severity:
                signals.append(_signal("amount_decrease", severity, f"{pct:.0f}% decrease", f"OpportunityFieldHistory/{h['Id']}"))
        elif arr and opp["Amount"] < arr:
            pct = (arr - opp["Amount"]) / arr * 100
            severity = "high" if pct > 15 else "medium" if pct > 5 else None
            if severity:
                signals.append(_signal("amount_decrease", severity, f"{pct:.0f}% below current ARR", f"Opportunity/{opp['Id']}"))

        # opp_stalled: days since last stage-change history entry
        stage_changes = [h for h in history if h.get("Field") == "StageName"]
        if stage_changes:
            last = max(stage_changes, key=lambda h: h["CreatedDate"])
            evidence_refs.append(f"OpportunityFieldHistory/{last['Id']}")
            days = _days_between(last["CreatedDate"], as_of)
            severity = "high" if days > 60 else "medium" if days > 30 else None
            if severity:
                signals.append(_signal("opp_stalled", severity, f"no stage change in {days} days", f"OpportunityFieldHistory/{last['Id']}"))

        # contract_downgrade: any cancelled/reduced Asset
        for asset in assets:
            if asset.get("Status") == "Cancelled" or asset.get("Quantity", 1) == 0:
                evidence_refs.append(f"Asset/{asset['Id']}")
                signals.append(_signal("contract_downgrade", "high", f"{asset['Product2Id']} cancelled", f"Asset/{asset['Id']}"))

    if not history:
        gaps.append("no OpportunityFieldHistory available — cannot assess stage velocity")

    return _packet("commercial", account_id, as_of, signals, gaps, evidence_refs)


# --- Relationship heuristics --------------------------------------------------

def generate_relationship_packet(account_id: str, as_of: str, records: dict[str, list[dict]]) -> dict:
    signals = []
    evidence_refs = []
    gaps = []

    cases = records.get("Case", [])
    contacts = records.get("Contact", [])
    roles = records.get("OpportunityContactRole", [])
    tasks = records.get("Task", [])
    events = records.get("Event", [])

    # case_volume_spike / support_escalation (counts and flags only — no Description/Subject text)
    open_cases = [c for c in cases if c.get("Status") == "Open"]
    escalated = [c for c in cases if c.get("IsEscalated")]
    critical = [c for c in cases if c.get("Priority") == "Critical"]
    for c in cases:
        evidence_refs.append(f"Case/{c['Id']}")

    if len(open_cases) >= 2:
        severity = "high" if len(open_cases) >= 3 else "medium"
        signals.append(_signal("case_volume_spike", severity, f"{len(open_cases)} open cases", f"Case/{open_cases[0]['Id']}"))

    if escalated or critical:
        severity = "high" if (len(escalated) >= 2 or critical) else "medium"
        ref = escalated[0]["Id"] if escalated else critical[0]["Id"]
        signals.append(_signal("support_escalation", severity, f"{len(escalated)} escalated case(s)", f"Case/{ref}"))

    # champion_departed: primary contact role -> inactive contact
    primary_roles = [r for r in roles if r.get("IsPrimary")]
    contacts_by_id = {c["Id"]: c for c in contacts}
    for role in primary_roles:
        contact = contacts_by_id.get(role["ContactId"])
        if contact and not contact.get("IsActive", True):
            evidence_refs.append(f"Contact/{contact['Id']}")
            signals.append(_signal("champion_departed", "high", f"primary contact {contact['Name']} inactive", f"Contact/{contact['Id']}"))

    # low_engagement: fewer than 2 contact roles on the renewal opportunity
    if roles:
        evidence_refs.append(f"OpportunityContactRole/{roles[0]['Id']}")
        if len(roles) <= 1:
            signals.append(_signal("low_engagement", "medium", f"{len(roles)} contact role(s)", f"OpportunityContactRole/{roles[0]['Id']}"))
    else:
        gaps.append("no OpportunityContactRole records — cannot assess engagement breadth")

    # no_recent_activity: latest Task/Event ActivityDate vs as_of
    activity_dates = [t["ActivityDate"] for t in tasks] + [e["ActivityDate"] for e in events]
    activity_refs = [f"Task/{t['Id']}" for t in tasks] + [f"Event/{e['Id']}" for e in events]
    evidence_refs.extend(activity_refs)
    if activity_dates:
        latest = max(activity_dates)
        days = _days_between(latest, as_of)
        severity = "high" if days > 90 else "medium" if days > 60 else None
        if severity:
            ref = activity_refs[activity_dates.index(latest)]
            signals.append(_signal("no_recent_activity", severity, f"no activity in {days} days", ref))
    else:
        gaps.append("no Task/Event records found — cannot assess recent engagement")

    return _packet("relationship", account_id, as_of, signals, gaps, evidence_refs)


# --- Synthesis (intentionally non-discriminating — see module docstring) -----

def generate_synthesis(account_id: str, packets: list[dict]) -> dict:
    citations = []
    for packet in packets:
        citations.extend(packet.get("evidence_refs", [])[:2])

    return {
        "account_id": account_id,
        "score": 81,
        "band": "high",
        "drivers": ["stub model: constant score, no discrimination — see evaluate.py Gate 1"],
        "citations": citations[:5],
        "abstained": False,
        "rationale": (
            "Stub model canned response — not a real assessment. Every account "
            "scores 81 under --dry-run by design; run with a real ANTHROPIC_API_KEY "
            "for actual scoring."
        ),
    }


# --- helpers -------------------------------------------------------------------

def _signal(name: str, severity: str, value: str, evidence_ref: str) -> dict:
    return {"name": name, "severity": severity, "value": value, "evidence_ref": evidence_ref}


def _packet(specialist: str, account_id: str, as_of: str, signals: list[dict], gaps: list[str], evidence_refs: list[str]) -> dict:
    return {
        "specialist": specialist,
        "account_id": account_id,
        "as_of": as_of,
        "signals": signals,
        "gaps": gaps,
        "evidence_refs": sorted(set(evidence_refs)),
        "verbatim_excluded": True,
    }


def _days_between(earlier: str, later: str) -> int:
    from datetime import datetime

    d1 = datetime.strptime(str(earlier)[:10], "%Y-%m-%d")
    d2 = datetime.strptime(str(later)[:10], "%Y-%m-%d")
    return (d2 - d1).days
