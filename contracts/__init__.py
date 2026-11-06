"""Shared schemas between compiler, enforce, and web.

Changes need all 3 approvals; bump SCHEMA_VERSION on every change.
"""

from contracts.verdict import Verdict

SCHEMA_VERSION = "0.1.0"

__all__ = ["SCHEMA_VERSION", "Verdict"]
