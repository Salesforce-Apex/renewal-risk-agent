# Renewal Risk Agent — v3 (simplified POC) — Documentation

## Part 1 — What this is

A multi-agent pipeline that, given a Salesforce account 120 days before
renewal, produces a one-page risk brief: a churn/downgrade score, cited
drivers, and declared gaps. It reads Salesforce, never writes to it.

```
TRIGGER  renewal_date − 120d  (or a golden-set CSV for backtesting)
   │
   ▼
COORDINATOR          claude-opus-5      no tools — planner only
   │                                    picks specialists, sets tool budget
   ├──────────────┬─────────────────────────────────────────────
   ▼              ▼
COMMERCIAL     RELATIONSHIP             claude-sonnet-5 (parallel)
Opportunity    Case, CaseHistory
OppFieldHist   Contact, OpportunityContactRole
Contract       Task, Event
Asset/CPQ
   │              │
   └──────┬───────┘
          ▼
     soql_guard          ← as-of enforcement + DML block. Built first.
          ▼
   SALESFORCE          soql_query · get_record · describe_object
   (mock now, MCP later) allowlist posture; all writes disabled
          │
   2 × EvidencePacket    typed · cited · declares its own gaps
          ▼
SYNTHESIS            claude-opus-5      packets only, never raw records
                                        scores, cites, may abstain
          ▼
OUTPUT               briefs/*.md · briefs.csv · runs.sqlite
                     no Salesforce write-back, no Slack, no email
```

This build is a **simplified POC**: it keeps every box in that diagram, but
`SALESFORCE` is `MockSalesforce` (canned fixture data, `mock_salesforce.py`)
and the four model calls are `stub_model.py` (schema-valid canned responses)
until real credentials and an API key are supplied. Swapping either in is a
`config.py` change, not a rewrite — see README.md's "Run it for real".

## Part 2 — The two hard gates

- **precision@20 ≥ 2× baseline** (baseline = your existing health score, or
  ARR descending — this build uses ARR descending since no health score is
  wired in).
- **faithfulness ≥ 95%** — manual. A CS ops analyst opens sampled
  `evidence_ref`s in Salesforce and confirms each driver. `evaluate.py`
  prepares the sample (`faithfulness_worksheet.csv`); the confirmation itself
  is not automatable and shouldn't be — it's the check on whether the model
  is telling the truth about what it read.

**Gate 0** runs before both: zero leakage violations
(`guard.audit_leakage`). If it finds anything, accuracy numbers from that run
are meaningless — `evaluate.py` refuses to print Gate 1 or the fabrication
check when Gate 0 fails.

`evaluate.py` also runs a **fabrication check**: every citation in a
RiskAssessment must resolve to an `evidence_ref` one of that account's own
packets actually emitted. A citation that doesn't is the model claiming a
source it was never given.

## Part 3 — Golden set

`golden_set.csv` columns: `account_id, name, arr, renewal_date, as_of, outcome`.

- `outcome ∈ churned / downgraded / renewed / expanded`
- `as_of` = 120 days before that account's renewal date
- Target: 80–120 accounts, ~30% churn/downgrade

`golden_set.example.csv` in this repo is a **4-row illustrative example**
built from the mock fixture accounts in `mock_salesforce.py` — enough to
exercise `run.py --golden` and every gate in `evaluate.py` mechanically.
Assembling the real 80–120 account set against your own org's outcomes is
half a day and it is the POC. Without known outcomes you have a demo, not a
result.

## Part 4 — Order of work

1. `test_guard.py` green.
2. Salesforce MCP connection verified on one account — check the integration
   user can actually **see** your target accounts. Record-level sharing
   bites here, and it looks like the agent missing data.
3. `signals.yaml` thresholds reviewed with a CS ops analyst (this build ships
   a starter set of 8 signals across the two specialists — treat it as a
   draft, not a final registry).
4. Golden set assembled.
5. One real account end to end. Read the packets by hand — this build's
   `runs.sqlite` ledger and rendered `briefs/*.md` are built for exactly this
   step. This is where you find that CSAT isn't a field in your org, or that
   `Case.AccountId` is null for 15% of cases because they're contact-linked
   only.
6. Full backtest → leakage audit → gates.
7. Shadow 30 accounts with 5 CSMs, 30% held back.

## Part 5 — Setup

### macOS / Linux

```
cd renewal-risk-agent
pip install -r requirements.txt
python3 test_guard.py
python3 run.py --dry-run
```

### Windows

Use `py` instead of `python3`, and a virtual environment is recommended so
`pip install` doesn't touch your system Python:

```
cd renewal-risk-agent
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py test_guard.py
py run.py --dry-run
```

Common errors:

- **`'python3' is not recognized`** — use `py` (or `python`) on Windows; this
  repo's own commands in README.md assume macOS/Linux.
- **`ModuleNotFoundError: No module named 'yaml'`** — `pip install -r
  requirements.txt` wasn't run in the same environment `py` resolves to.
  Confirm with `py -m pip show pyyaml`.
- **PowerShell blocks `.venv\Scripts\activate`** — run
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first, or use
  `cmd.exe` instead.
- **`ANTHROPIC_API_KEY`/`SALESFORCE_TOKEN` not picked up** — Windows env vars
  set with `set VAR=value` only last the current shell session; use
  `setx VAR value` for persistence, then open a new shell.

## Part 6 — Two things not to defer

**PII.** The `verbatim_excluded` rule is enforced in `schemas.py` and
`guard.strip_banned_fields` — Case bodies never enter a packet, only counts
and dates. Keep it even in the POC. It's also your prompt-injection
containment: Case text is customer-authored, specialists emit structured
fields only, so injected instructions have no path to the synthesis agent.
`mock_salesforce.py`'s Case fixtures deliberately include an adversarial
`Subject`/`Description` ("ignore prior instructions", "considering switching
vendors") precisely so `strip_banned_fields` has something real to strip in
the dry run — `test_guard.py`'s `test_strips_free_text_fields` pins this.

**ZDR.** The MCP connector is not covered by zero-data-retention
arrangements. Data exchanged with MCP servers, including tool definitions and
execution results, is retained under standard policy. If your org has a ZDR
agreement, raise this in week 0 — before `MCPSalesforce` is wired to
anything real.

## Part 7 — Deliberately absent

Stripe/PayPal · warehouse · identity resolution · Postgres · scheduler ·
secrets manager · Slack · email · Salesforce writes · rate-limit backoff.

Add a billing source in phase 2 only if you're monthly-billed or self-serve —
then payment behaviour is the churn event. For annual enterprise contracts,
`OpportunityFieldHistory` on `Amount` plus CPQ amendments (this build's
`Asset` records) cover the downgrade signal, and payment failures arrive too
late to act on.

## Part 8 — Cost

~$0.32/account uncached · ~$0.15 with prompt caching · ~$0.08 with Batch API.
100 accounts × 3 tuning passes ≈ $100 for the whole POC.

Rates in `config.py` are **placeholders** — verify at
https://claude.com/pricing before any cost slide.

## Part 9 — What's simplified vs. the original design, and why

| Original | This build | Why |
|---|---|---|
| Real Salesforce MCP | `MockSalesforce` fixture data | Run today, no credentials yet. Same interface (`salesforce_client.SalesforceClient`) — swap is a `config.py` flag. |
| Real Anthropic API calls | `stub_model.py` canned responses | Same reason. Packets are heuristic-driven off real (mock) data so they're worth reading by hand; Synthesis intentionally returns a constant score so `evaluate.py`'s Gate 1 has something real to fail against. |
| CS-ops-owned `signals.yaml` | Starter 8-signal registry | Placeholder until a CS ops analyst reviews thresholds (Part 4, step 3). |
| 80–120 account golden set | 4-row example | Illustrates the CSV contract and exercises every gate mechanically; the real set is explicitly the user's next step, not something a POC can fabricate meaningfully. |
