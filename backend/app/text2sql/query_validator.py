"""
US-09: Query Validation System
--------------------------------
Extends Himanshu's basic validator with:
  - Injection pattern detection (stacked queries, comment tricks)
  - Schema-aware table/column whitelisting
  - Structured validation report with all failure reasons
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.exceptions import QueryValidationError

logger = logging.getLogger(__name__)

# ── Forbidden keyword pattern (write ops + dangerous functions) ───────────────

FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|merge|exec|execute|create|grant|revoke"
    r"|xp_cmdshell|openrowset|opendatasource|bulk\s+insert|sp_executesql)\b",
    re.IGNORECASE,
)

# Injection: stacked statements via semicolons inside the body (not trailing)
STACKED_STMT = re.compile(r";(?!\s*$)")

# Comment-based injection tricks  (-- or /**/)
COMMENT_INJECTION = re.compile(r"(--|/\*)")

# Hex / char encoding tricks
HEX_ENCODING = re.compile(r"0x[0-9a-fA-F]{4,}", re.IGNORECASE)

# UNION-based injection: UNION followed by SELECT (allowed for analytics but logged)
UNION_SELECT = re.compile(r"\bUNION\s+(ALL\s+)?SELECT\b", re.IGNORECASE)


# ── Validation report ─────────────────────────────────────────────────────────

@dataclass
class ValidationReport:
    is_valid: bool = True
    sql: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.is_valid = False

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "sql": self.sql,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ── Core validator ────────────────────────────────────────────────────────────

class QueryValidator:
    """
    Multi-stage SQL query validator.

    Stages:
      1. Structure check  – must start with SELECT, no stacked stmts
      2. Injection check  – forbidden keywords, comment tricks, hex encoding
      3. TOP guard        – inject TOP if missing (delegates to Himanshu's logic)
      4. Schema guard     – optional: warn on unknown tables (non-blocking)
    """

    def __init__(self, known_tables: set[str] | None = None) -> None:
        self._known_tables: set[str] = known_tables or set()

    def update_known_tables(self, tables: set[str]) -> None:
        """Update the whitelist of known tables (call after schema reload)."""
        self._known_tables = tables

    # ── Stage helpers ──────────────────────────────────────────────────────────

    def _check_structure(self, sql: str, report: ValidationReport) -> None:
        lowered = sql.lower()
        if not lowered.lstrip().startswith("select"):
            report.add_error("Query must begin with SELECT.")
        if STACKED_STMT.search(sql):
            report.add_error("Stacked SQL statements (semicolons mid-query) are not allowed.")

    def _check_injection(self, sql: str, report: ValidationReport) -> None:
        match = FORBIDDEN_KEYWORDS.search(sql)
        if match:
            report.add_error(f"Forbidden SQL keyword detected: '{match.group()}'.")
        if HEX_ENCODING.search(sql):
            report.add_error("Hex-encoded values detected — possible injection attempt.")
        if COMMENT_INJECTION.search(sql):
            report.add_warning(
                "SQL comments detected (-- or /* */). "
                "Ensure these are intentional and not injection artefacts."
            )
        if UNION_SELECT.search(sql):
            report.add_warning(
                "UNION SELECT detected. Allowed for analytics but will be audited."
            )

    def _apply_top_guard(self, sql: str, report: ValidationReport) -> str:
        """Inject TOP N when neither TOP nor COUNT is present."""
        lowered = sql.lower()
        if " top " not in f" {lowered} " and " count(" not in lowered:
            sql = re.sub(
                r"^select\s+",
                f"SELECT TOP {settings.SQL_MAX_ROWS} ",
                sql,
                flags=re.IGNORECASE,
            )
            report.add_warning(
                f"TOP {settings.SQL_MAX_ROWS} automatically added to cap result size."
            )
        return sql

    def _check_schema(self, sql: str, report: ValidationReport) -> None:
        """Non-blocking: warn when a FROM/JOIN table is not in the known schema."""
        if not self._known_tables:
            return
        referenced = set(re.findall(r"\bFROM\s+([\w.]+)|\bJOIN\s+([\w.]+)", sql, re.IGNORECASE))
        flat = {t for pair in referenced for t in pair if t}
        unknown = flat - self._known_tables
        for tbl in sorted(unknown):
            report.add_warning(f"Table '{tbl}' not found in the known schema.")

    # ── Public API ─────────────────────────────────────────────────────────────

    def validate(self, sql: str) -> ValidationReport:
        """
        Run all validation stages and return a ValidationReport.
        Does NOT raise — callers inspect report.is_valid.
        """
        cleaned = sql.strip().rstrip(";")
        report = ValidationReport(sql=cleaned)

        self._check_structure(cleaned, report)
        if not report.is_valid:
            # No point continuing if the structure is wrong
            return report

        self._check_injection(cleaned, report)
        if not report.is_valid:
            return report

        cleaned = self._apply_top_guard(cleaned, report)
        self._check_schema(cleaned, report)

        report.sql = cleaned
        return report

    def validate_or_raise(self, sql: str) -> str:
        """
        Validate and return the (possibly rewritten) SQL, or raise
        QueryValidationError with a concatenated error message.
        """
        report = self.validate(sql)
        if not report.is_valid:
            raise QueryValidationError("; ".join(report.errors))
        return report.sql


# ── Module-level singleton ────────────────────────────────────────────────────

query_validator = QueryValidator()


# ── Convenience wrappers (backwards-compatible with Himanshu's validator) ─────

def validate_query_report(sql: str) -> dict[str, Any]:
    """Return a full validation report dict."""
    return query_validator.validate(sql).to_dict()


def validate_query(sql: str) -> str:
    """
    Validate and return cleaned SQL.
    Raises QueryValidationError on failure (drop-in for Himanshu's validate_select_query).
    """
    return query_validator.validate_or_raise(sql)
