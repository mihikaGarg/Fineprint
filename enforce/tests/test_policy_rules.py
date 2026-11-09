from datetime import date
from typing import Any

from contracts import BudgetState, Expense, RuleCitation, RuleOutcome, Ruleset, SpendRule, Verdict
from enforce import evaluate_expense


def _rule(rule_type: str, params: dict[str, Any], **kw: Any) -> SpendRule:
    quote = "policy text"
    return SpendRule(
        id=f"r_{rule_type}",
        name=rule_type,
        rule_type=rule_type,
        citation=RuleCitation(page=1, quote=quote, char_start=0, char_end=len(quote)),
        params=params,
        source=kw.get("source", "policy"),
        status=kw.get("status", "approved"),
    )


def _expense(amount: int, category: str = "meals", **kw: Any) -> Expense:
    return Expense(
        id="e",
        amount_cents=amount,
        date=date(2026, 6, 1),
        merchant=kw.pop("merchant", "Cafe"),
        category=category,
        **kw,
    )


def _verdict(rule: SpendRule, expense: Expense) -> tuple[Verdict, str | None]:
    result = evaluate_expense(
        expense, Ruleset(grant_id="p", grant_name="P", rules=[rule]), BudgetState()
    )
    return result.verdict, (result.traces[0].fix if result.traces else None)


def test_per_item_cap_review_and_block() -> None:
    review = _rule(
        "per_item_cap", {"cap_cents": 7_500, "categories": ["meals"], "action": "review"}
    )
    assert _verdict(review, _expense(7_500))[0] == Verdict.ALLOWED
    verdict, fix = _verdict(review, _expense(9_000))
    assert verdict == Verdict.NEEDS_REVIEW and fix == "Allowed at $75 or less"
    block = _rule("per_item_cap", {"cap_cents": 7_500, "categories": ["meals"], "action": "block"})
    assert _verdict(block, _expense(9_000))[0] == Verdict.BLOCKED
    assert (
        _verdict(block, _expense(90_000, category="software"))[0] == Verdict.ALLOWED
    )  # other category


def test_approval_required_by_role() -> None:
    rule = _rule(
        "approval_required",
        {
            "threshold_cents": 500_000,
            "approver_role": "finance_director",
            "categories": [],
            "action": "review",
        },
    )
    assert _verdict(rule, _expense(400_000, "equipment"))[0] == Verdict.ALLOWED
    verdict, fix = _verdict(rule, _expense(600_000, "equipment"))
    assert verdict == Verdict.NEEDS_REVIEW and fix == "Allowed with finance director approval"
    assert (
        _verdict(rule, _expense(600_000, "equipment", approvals=["manager"]))[0]
        == Verdict.NEEDS_REVIEW
    )
    assert (
        _verdict(rule, _expense(600_000, "equipment", approvals=["finance_director"]))[0]
        == Verdict.ALLOWED
    )


def test_merchant_restriction_and_receipts() -> None:
    merchant = _rule("merchant_restriction", {"merchants": ["Amazon"]})
    assert _verdict(merchant, _expense(4_000, merchant="AMAZON MKTPLACE"))[0] == Verdict.BLOCKED
    assert _verdict(merchant, _expense(4_000, merchant="Staples"))[0] == Verdict.ALLOWED
    receipt = _rule("receipt_required", {"threshold_cents": 2_500, "categories": []})
    assert _verdict(receipt, _expense(2_000))[0] == Verdict.ALLOWED
    assert _verdict(receipt, _expense(3_000))[0] == Verdict.NEEDS_REVIEW
    assert _verdict(receipt, _expense(3_000, has_receipt=True))[0] == Verdict.ALLOWED


def test_proposed_rules_are_not_enforced() -> None:
    rule = _rule("category_prohibition", {"prohibited_categories": ["alcohol"]}, status="proposed")
    assert _verdict(rule, _expense(5_000, "alcohol"))[0] == Verdict.ALLOWED


def test_grant_and_policy_stack_strictest_wins() -> None:
    grant = Ruleset(
        grant_id="g",
        grant_name="G",
        rules=[
            _rule(
                "per_item_cap",
                {"cap_cents": 20_000, "categories": ["meals"], "action": "block"},
                source="grant",
            )
        ],
    )
    policy = Ruleset(
        grant_id="p",
        grant_name="P",
        rules=[
            _rule("per_item_cap", {"cap_cents": 7_500, "categories": ["meals"], "action": "review"})
        ],
    )
    result = evaluate_expense(_expense(9_000), [grant, policy], BudgetState())
    assert result.verdict == Verdict.NEEDS_REVIEW
    deciding = next(t for t in result.traces if t.outcome != RuleOutcome.PASS)
    assert deciding.source == "policy"
    result = evaluate_expense(_expense(25_000), [grant, policy], BudgetState())
    assert result.verdict == Verdict.BLOCKED


def test_every_non_pass_trace_has_a_fix() -> None:
    rules = [
        _rule("category_prohibition", {"prohibited_categories": ["meals"]}),
        _rule("per_item_cap", {"cap_cents": 100, "categories": [], "action": "review"}),
        _rule("receipt_required", {"threshold_cents": 0, "categories": []}),
    ]
    result = evaluate_expense(
        _expense(5_000), Ruleset(grant_id="p", grant_name="P", rules=rules), BudgetState()
    )
    assert all(t.fix for t in result.traces if t.outcome != RuleOutcome.PASS)
    assert all(t.fix is None for t in result.traces if t.outcome == RuleOutcome.PASS)


def _ladder() -> Ruleset:
    tiers = [(100_000, "manager"), (1_000_000, "department_director"), (5_000_000, "cfo")]
    rules = [
        _rule("approval_required", {"threshold_cents": t, "approver_role": r, "categories": []})
        for t, r in tiers
    ]
    rules.append(
        _rule(
            "approval_required",
            {"threshold_cents": 0, "approver_role": "it", "categories": ["software"]},
        )
    )
    for i, rule in enumerate(rules):
        rule.id = f"r_{i}"
    return Ruleset(grant_id="p", grant_name="P", rules=rules)


def test_higher_approver_covers_lower_tiers() -> None:
    result = evaluate_expense(
        _expense(6_000_000, category="equipment", approvals=["CFO"]), _ladder(), BudgetState()
    )
    assert result.verdict == Verdict.ALLOWED
    assert "Covered by CFO approval, which sits above manager" in [t.reason for t in result.traces]


def test_lower_approver_does_not_cover_higher_tier() -> None:
    result = evaluate_expense(
        _expense(6_000_000, category="equipment", approvals=["Manager"]), _ladder(), BudgetState()
    )
    assert result.verdict == Verdict.NEEDS_REVIEW
    failed = [t for t in result.traces if t.outcome != RuleOutcome.PASS]
    assert {t.reason for t in failed} == {
        "$60,000 needs department director approval",
        "$60,000 needs CFO approval",
    }
    director = next(t for t in failed if "director" in t.reason)
    assert director.fix == "Allowed with department director approval, or from someone above (CFO)"


def test_category_approval_is_not_part_of_the_ladder() -> None:
    # The CFO outranks the manager, but IT approval for software is a different check.
    result = evaluate_expense(
        _expense(200_000, category="software", approvals=["CFO"]), _ladder(), BudgetState()
    )
    assert result.verdict == Verdict.NEEDS_REVIEW
    assert [t.reason for t in result.traces if t.outcome != RuleOutcome.PASS] == [
        "$2,000 needs IT approval"
    ]


def test_company_approver_does_not_cover_grant_tier() -> None:
    grant = Ruleset(
        grant_id="g",
        grant_name="G",
        rules=[
            _rule(
                "approval_required",
                {"threshold_cents": 100_000, "approver_role": "program_officer", "categories": []},
                source="grant",
            )
        ],
    )
    result = evaluate_expense(
        _expense(6_000_000, category="equipment", approvals=["CFO"]),
        [_ladder(), grant],
        BudgetState(),
    )
    assert result.verdict == Verdict.NEEDS_REVIEW
    assert [t.reason for t in result.traces if t.outcome != RuleOutcome.PASS] == [
        "$60,000 needs program officer approval"
    ]
