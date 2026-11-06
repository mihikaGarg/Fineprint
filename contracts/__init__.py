"""Shared schemas between compiler, enforce, and web.

Changes need all 3 approvals; bump SCHEMA_VERSION on every change.
"""

from contracts.models import (
    BudgetLine,
    BudgetState,
    EnforcementResult,
    Expense,
    RuleCitation,
    RuleOutcome,
    Ruleset,
    RuleTrace,
    SpendRule,
)
from contracts.verdict import Verdict

SCHEMA_VERSION = "0.2.0"

__all__ = [
    "SCHEMA_VERSION",
    "BudgetLine",
    "BudgetState",
    "EnforcementResult",
    "Expense",
    "RuleCitation",
    "RuleOutcome",
    "RuleTrace",
    "Ruleset",
    "SpendRule",
    "Verdict",
]
