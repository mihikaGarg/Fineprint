"""Shared schemas between compiler, enforce, and web.

Changes need all 3 approvals; bump SCHEMA_VERSION on every change and run
`make schema` to regenerate contracts/schema/.
"""

from contracts.category import ExpenseCategory
from contracts.citation import ClauseCitation, SourceDocument
from contracts.expense import BudgetState, Expense
from contracts.rules import (
    BudgetLineCap,
    CategoryProhibition,
    PeriodOfPerformance,
    PerItemThreshold,
    PriorApprovalRequired,
    Rule,
    Ruleset,
    ThresholdAction,
)
from contracts.verdict import Decision, RuleEvaluation, RuleOutcome, Verdict, aggregate

SCHEMA_VERSION = "0.2.0"

__all__ = [
    "SCHEMA_VERSION",
    "BudgetLineCap",
    "BudgetState",
    "CategoryProhibition",
    "ClauseCitation",
    "Decision",
    "Expense",
    "ExpenseCategory",
    "PerItemThreshold",
    "PeriodOfPerformance",
    "PriorApprovalRequired",
    "Rule",
    "RuleEvaluation",
    "RuleOutcome",
    "Ruleset",
    "SourceDocument",
    "ThresholdAction",
    "Verdict",
    "aggregate",
]
