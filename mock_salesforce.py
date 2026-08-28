"""
mock_salesforce.py — canned Salesforce records for four fixture accounts with
distinct risk profiles. Stands in for a real org until SALESFORCE_MCP_URL /
SALESFORCE_TOKEN are supplied (see salesforce_client.py).

Every record carries `AccountId` directly (even history/junction objects that
would normally require a join through Opportunity/Case) — a simplification
that's fine for a mock and called out as a gap in DOCUMENTATION.md; a real
org requires actual joins, which MCPSalesforce's SOQL will do for real.

Every date is expressed relative to each account's own `as_of` so the fixture
data stays "120 days before renewal" no matter which as_of the CLI is run
with, provided --as-of is left at each account's default (2026-05-01) or the
golden CSV's as_of column is used consistently.
"""
from __future__ import annotations

ACCOUNTS = {
    "ACC-HEALTHY-001": {
        "name": "Northwind Robotics",
        "arr": 240_000,
        "renewal_date": "2026-08-29",
        "as_of": "2026-05-01",
        "profile": "healthy",
    },
    "ACC-STALLED-002": {
        "name": "Blue Harbor Logistics",
        "arr": 180_000,
        "renewal_date": "2026-08-29",
        "as_of": "2026-05-01",
        "profile": "stalled",
    },
    "ACC-ESCALATING-003": {
        "name": "Fernbank Health Systems",
        "arr": 410_000,
        "renewal_date": "2026-08-29",
        "as_of": "2026-05-01",
        "profile": "escalating",
    },
    "ACC-CHURNING-004": {
        "name": "Ridgeline Materials",
        "arr": 95_000,
        "renewal_date": "2026-08-29",
        "as_of": "2026-05-01",
        "profile": "churning",
    },
}

# --- Opportunity -----------------------------------------------------------

OPPORTUNITY = [
    dict(Id="0061-H", AccountId="ACC-HEALTHY-001", Name="Northwind Robotics — Renewal FY27",
         Amount=252000, StageName="Negotiation", CloseDate="2026-08-29", CreatedDate="2026-02-01"),
    dict(Id="0061-S", AccountId="ACC-STALLED-002", Name="Blue Harbor Logistics — Renewal FY27",
         Amount=180000, StageName="Proposal Sent", CloseDate="2026-08-29", CreatedDate="2026-01-15"),
    dict(Id="0061-E", AccountId="ACC-ESCALATING-003", Name="Fernbank Health Systems — Renewal FY27",
         Amount=410000, StageName="Negotiation", CloseDate="2026-08-29", CreatedDate="2026-02-10"),
    dict(Id="0061-C", AccountId="ACC-CHURNING-004", Name="Ridgeline Materials — Renewal FY27",
         Amount=68000, StageName="Proposal Sent", CloseDate="2026-08-29", CreatedDate="2026-01-05"),
]

OPPORTUNITY_FIELD_HISTORY = [
    dict(Id="H1", AccountId="ACC-HEALTHY-001", OpportunityId="0061-H", Field="StageName",
         OldValue="Qualification", NewValue="Negotiation", CreatedDate="2026-04-10"),
    dict(Id="H2", AccountId="ACC-STALLED-002", OpportunityId="0061-S", Field="StageName",
         OldValue="Qualification", NewValue="Proposal Sent", CreatedDate="2026-02-20"),
    # no further stage movement since Feb 20 -> stalled ~70 days as of 2026-05-01
    dict(Id="H3", AccountId="ACC-ESCALATING-003", OpportunityId="0061-E", Field="StageName",
         OldValue="Qualification", NewValue="Negotiation", CreatedDate="2026-04-01"),
    dict(Id="H4", AccountId="ACC-CHURNING-004", OpportunityId="0061-C", Field="Amount",
         OldValue="95000", NewValue="68000", CreatedDate="2026-03-15"),
]

# --- Contract / Asset (CPQ) --------------------------------------------------

CONTRACT = [
    dict(Id="C-H", AccountId="ACC-HEALTHY-001", ARR__c=240000, ContractTerm=12, CreatedDate="2025-08-29"),
    dict(Id="C-S", AccountId="ACC-STALLED-002", ARR__c=180000, ContractTerm=12, CreatedDate="2025-08-29"),
    dict(Id="C-E", AccountId="ACC-ESCALATING-003", ARR__c=410000, ContractTerm=12, CreatedDate="2025-08-29"),
    dict(Id="C-C", AccountId="ACC-CHURNING-004", ARR__c=95000, ContractTerm=12, CreatedDate="2025-08-29"),
]

ASSET = [
    dict(Id="A-H1", AccountId="ACC-HEALTHY-001", Product2Id="PROD-CORE", Quantity=50, Status="Active", CreatedDate="2025-08-29"),
    dict(Id="A-S1", AccountId="ACC-STALLED-002", Product2Id="PROD-CORE", Quantity=30, Status="Active", CreatedDate="2025-08-29"),
    dict(Id="A-E1", AccountId="ACC-ESCALATING-003", Product2Id="PROD-CORE", Quantity=80, Status="Active", CreatedDate="2025-08-29"),
    dict(Id="A-C1", AccountId="ACC-CHURNING-004", Product2Id="PROD-CORE", Quantity=20, Status="Active", CreatedDate="2025-08-29"),
    dict(Id="A-C2", AccountId="ACC-CHURNING-004", Product2Id="PROD-ADDON", Quantity=0, Status="Cancelled", CreatedDate="2026-02-01"),
]

# --- Case / CaseHistory (free-text fields present, guard strips them) ------

CASE = [
    dict(Id="500-H1", AccountId="ACC-HEALTHY-001", CaseNumber="00001", Priority="Low",
         IsEscalated=False, Status="Closed", CreatedDate="2026-03-01",
         Subject="minor question about SSO config", Description="customer asked about SAML setup"),

    dict(Id="500-S1", AccountId="ACC-STALLED-002", CaseNumber="00010", Priority="Medium",
         IsEscalated=False, Status="Closed", CreatedDate="2026-02-15",
         Subject="billing question", Description="wanted invoice detail"),

    dict(Id="500-E1", AccountId="ACC-ESCALATING-003", CaseNumber="00020", Priority="Critical",
         IsEscalated=True, Status="Open", CreatedDate="2026-04-20",
         Subject="production outage impacting patient records", Description="P1 outage, escalated to eng"),
    dict(Id="500-E2", AccountId="ACC-ESCALATING-003", CaseNumber="00021", Priority="High",
         IsEscalated=True, Status="Open", CreatedDate="2026-04-22",
         Subject="data sync failure", Description="nightly sync job failing 3 days running"),
    dict(Id="500-E3", AccountId="ACC-ESCALATING-003", CaseNumber="00022", Priority="Medium",
         IsEscalated=False, Status="Closed", CreatedDate="2026-04-05",
         Subject="performance degradation", Description="slow dashboard load"),

    dict(Id="500-C1", AccountId="ACC-CHURNING-004", CaseNumber="00030", Priority="High",
         IsEscalated=True, Status="Open", CreatedDate="2026-03-10",
         Subject="considering switching vendors", Description="customer explicitly said they are evaluating competitor X"),
    dict(Id="500-C2", AccountId="ACC-CHURNING-004", CaseNumber="00031", Priority="Medium",
         IsEscalated=False, Status="Closed", CreatedDate="2026-04-01",
         Subject="feature gap vs competitor", Description="missing reporting feature, cited as blocker"),
    dict(Id="500-C3", AccountId="ACC-CHURNING-004", CaseNumber="00032", Priority="Low",
         IsEscalated=False, Status="Closed", CreatedDate="2026-01-20",
         Subject="onboarding follow-up", Description="routine check-in"),
]

CASE_HISTORY = [
    dict(Id="CH1", AccountId="ACC-ESCALATING-003", CaseId="500-E1", Field="Priority",
         OldValue="High", NewValue="Critical", CreatedDate="2026-04-21"),
    dict(Id="CH2", AccountId="ACC-CHURNING-004", CaseId="500-C1", Field="IsEscalated",
         OldValue="False", NewValue="True", CreatedDate="2026-03-11"),
]

# --- Contact / OpportunityContactRole ---------------------------------------

CONTACT = [
    dict(Id="003-H1", AccountId="ACC-HEALTHY-001", Name="Dana Whitfield", Title="VP Operations",
         IsActive=True, CreatedDate="2024-01-01"),

    dict(Id="003-S1", AccountId="ACC-STALLED-002", Name="Marcus Ihejirika", Title="Director IT",
         IsActive=True, CreatedDate="2024-03-01"),

    dict(Id="003-E1", AccountId="ACC-ESCALATING-003", Name="Priya Natarajan", Title="CIO",
         IsActive=True, CreatedDate="2023-11-01"),
    dict(Id="003-E2", AccountId="ACC-ESCALATING-003", Name="Tomas Berger", Title="IT Manager",
         IsActive=True, CreatedDate="2024-06-01"),

    dict(Id="003-C1", AccountId="ACC-CHURNING-004", Name="Elena Suárez", Title="VP Supply Chain",
         IsActive=False, CreatedDate="2023-05-01"),  # champion departed
]

OPPORTUNITY_CONTACT_ROLE = [
    dict(Id="OCR-H1", AccountId="ACC-HEALTHY-001", OpportunityId="0061-H", ContactId="003-H1",
         IsPrimary=True, Role="Decision Maker", CreatedDate="2026-02-01"),

    dict(Id="OCR-S1", AccountId="ACC-STALLED-002", OpportunityId="0061-S", ContactId="003-S1",
         IsPrimary=True, Role="Decision Maker", CreatedDate="2026-01-15"),
    # only 1 contact role -> low_engagement signal

    dict(Id="OCR-E1", AccountId="ACC-ESCALATING-003", OpportunityId="0061-E", ContactId="003-E1",
         IsPrimary=True, Role="Economic Buyer", CreatedDate="2026-02-10"),
    dict(Id="OCR-E2", AccountId="ACC-ESCALATING-003", OpportunityId="0061-E", ContactId="003-E2",
         IsPrimary=False, Role="Technical Buyer", CreatedDate="2026-02-10"),

    dict(Id="OCR-C1", AccountId="ACC-CHURNING-004", OpportunityId="0061-C", ContactId="003-C1",
         IsPrimary=True, Role="Decision Maker", CreatedDate="2026-01-05"),
    # primary contact (003-C1) IsActive=False -> champion_departed signal
]

# --- Task / Event ------------------------------------------------------------

TASK = [
    dict(Id="00T-H1", AccountId="ACC-HEALTHY-001", ActivityDate="2026-04-25", Status="Completed",
         Subject="QBR follow-up call", CreatedDate="2026-04-25"),
    dict(Id="00T-H2", AccountId="ACC-HEALTHY-001", ActivityDate="2026-04-10", Status="Completed",
         Subject="Check-in call", CreatedDate="2026-04-10"),

    dict(Id="00T-S1", AccountId="ACC-STALLED-002", ActivityDate="2026-02-01", Status="Completed",
         Subject="Renewal kickoff", CreatedDate="2026-02-01"),
    # nothing logged since Feb 1 -> no_recent_activity as of 2026-05-01

    dict(Id="00T-E1", AccountId="ACC-ESCALATING-003", ActivityDate="2026-04-23", Status="Completed",
         Subject="P1 incident bridge", CreatedDate="2026-04-23"),

    dict(Id="00T-C1", AccountId="ACC-CHURNING-004", ActivityDate="2026-01-25", Status="Completed",
         Subject="Onboarding check-in", CreatedDate="2026-01-25"),
    # nothing logged since Jan 25 -> no_recent_activity
]

EVENT = [
    dict(Id="00U-H1", AccountId="ACC-HEALTHY-001", ActivityDate="2026-04-15",
         Subject="Quarterly business review", CreatedDate="2026-04-15"),
    dict(Id="00U-E1", AccountId="ACC-ESCALATING-003", ActivityDate="2026-04-24",
         Subject="Exec escalation sync", CreatedDate="2026-04-24"),
]

OBJECTS = {
    "Opportunity": OPPORTUNITY,
    "OpportunityFieldHistory": OPPORTUNITY_FIELD_HISTORY,
    "Contract": CONTRACT,
    "Asset": ASSET,
    "Case": CASE,
    "CaseHistory": CASE_HISTORY,
    "Contact": CONTACT,
    "OpportunityContactRole": OPPORTUNITY_CONTACT_ROLE,
    "Task": TASK,
    "Event": EVENT,
}


def records_for(object_name: str, account_id: str) -> list[dict]:
    """All mock records of `object_name` belonging to `account_id`."""
    return [r for r in OBJECTS.get(object_name, []) if r.get("AccountId") == account_id]
