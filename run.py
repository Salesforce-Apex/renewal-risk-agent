#!/usr/bin/env python3
"""
run.py — CLI entry point.

    python3 run.py --dry-run                                   # all 4 fixture accounts, stub model
    python3 run.py --dry-run --account ACC-CHURNING-004
    python3 run.py --dry-run --golden golden_set.example.csv
    python3 run.py --account 0018c00002LmNqRAAZ --as-of 2026-05-01   # real run, needs creds
    python3 run.py --golden golden_set.csv --concurrency 4
"""
from __future__ import annotations

import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import agent
import config
import mock_salesforce


def _run_one(account_id: str, as_of: str, account_name: str | None = None) -> agent.RunResult:
    result = agent.run_account(account_id, as_of)
    agent.write_brief(result, account_name)
    agent.append_briefs_csv(result, account_name)
    return result


def _print_summary(results: list[agent.RunResult]) -> None:
    print(f"\n{'account_id':<22} {'score':>6} {'band':<8} {'abstained':<10} {'leakage':<8}")
    for r in results:
        a = r.assessment
        print(f"{r.account_id:<22} {a['score']:>6} {a['band']:<8} {str(a['abstained']):<10} {len(r.leakage_violations):<8}")


def run_dry_run_fixtures() -> list[agent.RunResult]:
    results = []
    for account_id, meta in mock_salesforce.ACCOUNTS.items():
        result = _run_one(account_id, meta["as_of"], meta["name"])
        results.append(result)
    return results


def run_golden(csv_path: str, concurrency: int) -> list[agent.RunResult]:
    with open(csv_path) as f:
        rows = list(csv.DictReader(f))

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {
            pool.submit(_run_one, row["account_id"], row["as_of"], row.get("name")): row
            for row in rows
        }
        for future in as_completed(futures):
            row = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001 - surface per-account failure, keep going
                print(f"FAILED {row['account_id']}: {exc}", file=sys.stderr)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Renewal Risk Agent — run a renewal-risk pipeline for one or more accounts.")
    parser.add_argument("--dry-run", action="store_true", help="Use the stub model + mock Salesforce data (no credentials needed).")
    parser.add_argument("--account", help="Single Salesforce account Id to run.")
    parser.add_argument("--as-of", help="As-of date (YYYY-MM-DD). Required with --account unless it's a mock fixture id.")
    parser.add_argument("--golden", help="Path to a golden-set CSV (account_id,name,arr,renewal_date,as_of,outcome).")
    parser.add_argument("--concurrency", type=int, default=4, help="Max parallel accounts for --golden runs.")
    args = parser.parse_args()

    if args.dry_run:
        config.USE_STUB = True

    if args.golden:
        results = run_golden(args.golden, args.concurrency)
    elif args.account:
        as_of = args.as_of or mock_salesforce.ACCOUNTS.get(args.account, {}).get("as_of")
        if not as_of:
            parser.error("--as-of is required for accounts that aren't mock fixtures")
        results = [_run_one(args.account, as_of)]
    elif args.dry_run:
        results = run_dry_run_fixtures()
    else:
        parser.error("specify --account, --golden, or --dry-run")
        return 2

    _print_summary(results)
    print(f"\nBriefs written to {config.BRIEFS_DIR}/, rollup in {config.BRIEFS_CSV}, ledger in {config.RUNS_DB}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
