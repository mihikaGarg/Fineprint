"""ENFORCE path: expense + ruleset + budget state -> verdict + clause trace.

Deterministic, no LLM calls, target <100ms. Owner: B.
"""

from enforce.engine import evaluate_expense
from enforce.rules import evaluate_rule, is_rule_applicable

__all__ = ["evaluate_expense", "evaluate_rule", "is_rule_applicable"]
