"""
salesforce_client.py — one interface, two implementations.

  MockSalesforce  — reads from mock_salesforce.py. Used for --dry-run and for
                    local development before real org access is wired up.
  MCPSalesforce   — calls the Salesforce MCP (soql_query / get_record /
                    describe_object). Writes are never exposed. Left
                    non-functional (raises) until SALESFORCE_TOKEN and
                    SALESFORCE_MCP_URL are set — see config.py.

Every read from either implementation passes through guard.soql_guard /
guard.strip_banned_fields first. Specialists (commercial.py-equivalent logic
in agent.py) never see an unguarded record.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

import guard
import mock_salesforce

_FROM_RE = re.compile(r"\bFROM\s+(\w+)", re.IGNORECASE)
_ACCOUNT_ID_RE = re.compile(r"AccountId\s*=\s*'([^']+)'", re.IGNORECASE)


class SalesforceClient(ABC):
    @abstractmethod
    def soql_query(self, soql: str, as_of_date: str) -> list[dict]:
        ...

    @abstractmethod
    def get_record(self, object_name: str, record_id: str) -> dict | None:
        ...

    @abstractmethod
    def describe_object(self, object_name: str) -> dict:
        ...


def _extract_object(soql: str) -> str | None:
    match = _FROM_RE.search(soql)
    return match.group(1) if match else None


def _extract_account_id(soql: str) -> str | None:
    match = _ACCOUNT_ID_RE.search(soql)
    return match.group(1) if match else None


def _passes_as_of(record: dict, as_of_date: str) -> bool:
    """Mirror what the guard-injected WHERE clause would enforce, against
    the mock data directly (the mock has no real SOQL engine to run the
    injected clause against)."""
    violations = guard.audit_leakage([record], as_of_date)
    return len(violations) == 0


class MockSalesforce(SalesforceClient):
    """Dry-run / local-dev data source. No network, no credentials."""

    def soql_query(self, soql: str, as_of_date: str) -> list[dict]:
        # Validates read-only + as-of enforceability; raises GuardViolation on DML.
        guard.soql_guard(soql, as_of_date)

        object_name = _extract_object(soql)
        account_id = _extract_account_id(soql)
        if object_name is None:
            raise ValueError(f"could not parse object name from SOQL: {soql!r}")

        records = (
            mock_salesforce.records_for(object_name, account_id)
            if account_id
            else list(mock_salesforce.OBJECTS.get(object_name, []))
        )
        records = [r for r in records if _passes_as_of(r, as_of_date)]

        cleaned = []
        for record in records:
            safe_record, _stripped = guard.strip_banned_fields(record)
            cleaned.append(safe_record)
        return cleaned

    def get_record(self, object_name: str, record_id: str) -> dict | None:
        for record in mock_salesforce.OBJECTS.get(object_name, []):
            if record.get("Id") == record_id:
                safe_record, _stripped = guard.strip_banned_fields(record)
                return safe_record
        return None

    def describe_object(self, object_name: str) -> dict:
        records = mock_salesforce.OBJECTS.get(object_name, [])
        fields = sorted(records[0].keys()) if records else []
        return {"name": object_name, "fields": fields}


class MCPSalesforce(SalesforceClient):
    """
    Real Salesforce MCP connector. Not functional until SALESFORCE_TOKEN and
    SALESFORCE_MCP_URL are configured (see config.py) and the MCP tool
    definitions (soql_query / get_record / describe_object) are wired to an
    actual MCP client call. Writes are not exposed by design — there is no
    insert/update/delete method on this class, and guard.soql_guard blocks
    any DML that somehow reached soql_query anyway.
    """

    def __init__(self, mcp_url: str | None, token: str | None):
        self.mcp_url = mcp_url
        self.token = token

    def _require_connection(self):
        if not self.mcp_url or not self.token:
            raise RuntimeError(
                "MCPSalesforce is not configured. Set SALESFORCE_MCP_URL and "
                "SALESFORCE_TOKEN, then wire the MCP tool calls in "
                "salesforce_client.MCPSalesforce. Use --dry-run (MockSalesforce) "
                "until then."
            )

    def soql_query(self, soql: str, as_of_date: str) -> list[dict]:
        guard.soql_guard(soql, as_of_date)  # validate before we ever touch the network
        self._require_connection()
        raise NotImplementedError("MCP soql_query call not yet wired — see class docstring.")

    def get_record(self, object_name: str, record_id: str) -> dict | None:
        self._require_connection()
        raise NotImplementedError("MCP get_record call not yet wired — see class docstring.")

    def describe_object(self, object_name: str) -> dict:
        self._require_connection()
        raise NotImplementedError("MCP describe_object call not yet wired — see class docstring.")


def get_client(use_stub: bool, mcp_url: str | None = None, token: str | None = None) -> SalesforceClient:
    if use_stub:
        return MockSalesforce()
    return MCPSalesforce(mcp_url, token)
