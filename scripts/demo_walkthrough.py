"""Narrated end-to-end demo against the real API (in-process). Run: make demo

The policy-reading step uses a recorded Claude-style answer because no real
API key is set; every other step is the real code path.
"""

import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any

os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ["FINEPRINT_PROPOSER"] = "keyword"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import api.main as api
from shared.llm import LLMRequest, LLMResponse

POLICY = (
    "Our travel and expense policy: No alcohol on company or grant funds. "
    "Meals up to $75 per person. Anything over $5,000 needs approval from the finance director. "
    "Never buy from Amazon. Receipts are required for anything over $25. "
    "Hotels up to $250 per night. Please submit expenses within 30 days."
)


def r(rule_type: str, quote: str, **kw: Any) -> dict[str, Any]:
    return {
        "rule_type": rule_type,
        "quote": quote,
        "categories": kw.get("categories", []),
        "action": kw.get("action", "unspecified"),
        "approver_role": kw.get("approver_role", ""),
        "merchants": kw.get("merchants", []),
        "questions": kw.get("questions", []),
    }


RECORDED = {
    "rules": [
        r("category_prohibition", "No alcohol on company or grant funds.", categories=["alcohol"]),
        r("per_item_cap", "Meals up to $75 per person.", categories=["meals"]),
        r(
            "approval_required",
            "Anything over $5,000 needs approval from the finance director.",
            approver_role="finance_director",
        ),
        r("merchant_restriction", "Never buy from Amazon.", merchants=["Amazon"]),
        r("receipt_required", "Receipts are required for anything over $25."),
        r("per_item_cap", "Hotels up to $250 per night.", categories=["lodging"], action="review"),
    ],
    "not_rules": [
        {
            "quote": "Please submit expenses within 30 days.",
            "why": "A submission deadline, not a spending rule",
        }
    ],
}


def recorded_claude(request: LLMRequest) -> LLMResponse:
    return LLMResponse(text=json.dumps(RECORDED), model="recorded", input_tokens=0, output_tokens=0)


api.LLM_TRANSPORT = recorded_claude
c = TestClient(api.app)


def h(title: str) -> None:
    print(f"\n{'=' * 78}\n  {title}\n{'=' * 78}")


def wrap(s: str, indent: str = "     ") -> str:
    return textwrap.fill(s, 78, initial_indent=indent, subsequent_indent=indent)


ICON = {"ALLOWED": "✅ ALLOWED", "BLOCKED": "⛔ BLOCKED", "NEEDS_REVIEW": "🔶 NEEDS REVIEW"}

# 1. Grant ------------------------------------------------------------------
h("STEP 1  Upload the grant agreement (demo_grant.pdf, 4 pages)")
g = c.post("/api/compile/demo").json()
cov = g["coverage"]
print(f"  Rule finder: {g['proposer']}  (offline; Claude would also find 2 more)")
print(
    f"  Coverage: read all {cov['total']} clauses -> {cov['rules']} became rules, "
    f"{cov['rejected']} rejected, {cov['flagged']} flagged, {cov['no_rule']} no rule"
)
for rule in g["ruleset"]["rules"]:
    ci = rule["citation"]
    print(f'   • {rule["name"]:<24} p.{ci["page"]}  "{ci["quote"][:60]}…"')
for x in g["rejected"]:
    print(f'   ✗ rejected: {x["reason"]}  "{x["candidate"]["quote"][:50]}…"')
grant_id = g["ruleset"]["grant_id"]

# 2. Policy -----------------------------------------------------------------
h("STEP 2  Type the company's own rules in plain English")
print(wrap(f'"{POLICY}"', "  "))
d = c.post("/api/policy/draft", json={"text": POLICY, "name": "Lakeview expense policy"}).json()
print("\n  [policy reading uses a RECORDED Claude-style answer; key not set]")
print(f"\n  Rules drafted (all PROPOSED, not enforced yet): {len(d['ruleset']['rules'])}")
for rule in d["ruleset"]["rules"]:
    print(f'   • {rule["name"]:<20} from your words: "{rule["citation"]["quote"]}"')
for x in d["rejected"]:
    print(f'   ✗ not turned into a rule: "{x["candidate"]["quote"]}" -> {x["reason"]}')
for n in d["not_rules"]:
    print(f'   - skipped: "{n["quote"]}" ({n["why"]})')

# 3. Questions --------------------------------------------------------------
h("STEP 3  Quick multiple-choice questions where the rules were unclear")
answers: dict[str, str] = {}
for q in d["questions"]:
    print(f"  Q: {q['question']}")
    for i, o in enumerate(q["options"]):
        print(f"     ({chr(65 + i)}) {o['label']}")
    pick = "review" if "Meals" in q["question"] else "block"
    label = next(o["label"] for o in q["options"] if o["value"] == pick)
    print(f"     → user taps: {label}\n")
    answers[q["id"]] = pick
d = c.post(f"/api/policy/{d['draft_id']}/answers", json={"answers": answers}).json()
policy_id = d["draft_id"]
print(f"  Open questions left: {len(d['questions'])}")

# 4. Review -----------------------------------------------------------------
h("STEP 4  Review rule cards (examples run through the real engine), then approve")
for card in c.get(f"/api/rulesets/{policy_id}/cards").json():
    print(f'  {card["rule"]["name"]}: "{card["rule"]["citation"]["quote"]}"')
    for e in card["examples"]:
        print(f"     {e['description']:<34} → {ICON[e['verdict']]}")
c.post(f"/api/rulesets/{policy_id}/approve", json={})
c.post(f"/api/rulesets/{grant_id}/approve", json={})
print("\n  ✔ Company policy approved   ✔ Grant rules approved   (now enforced)")

# 5. Expenses ---------------------------------------------------------------
h("STEP 5  Expenses come in, checked against BOTH rulebooks at once")
budget = {
    "lines": {
        "travel_domestic": {
            "category": "travel_domestic",
            "allocated_cents": 800000,
            "spent_cents": 320000,
        },
        "equipment": {"category": "equipment", "allocated_cents": 2000000, "spent_cents": 0},
    }
}
EXPENSES = [
    (
        "Team lunch, Lakeview Cafe",
        6_200,
        "meals",
        "Lakeview Cafe",
        "2026-06-15",
        {"has_receipt": True},
    ),
    (
        "Client dinner, Harbor Grill",
        9_600,
        "meals",
        "Harbor Grill",
        "2026-06-16",
        {"has_receipt": True},
    ),
    (
        "Drinks, Riverside Wine Bar",
        4_800,
        "alcohol",
        "Riverside Wine Bar",
        "2026-06-16",
        {"has_receipt": True},
    ),
    (
        "Printer paper, Amazon",
        3_500,
        "supplies",
        "Amazon Marketplace",
        "2026-06-17",
        {"has_receipt": True},
    ),
    (
        "Microscope, Meridian Optics",
        1_240_000,
        "equipment",
        "Meridian Optics",
        "2026-07-01",
        {"has_receipt": True},
    ),
    (
        "Microscope, with finance director OK",
        1_240_000,
        "equipment",
        "Meridian Optics",
        "2026-07-01",
        {"has_receipt": True, "approvals": ["finance_director"]},
    ),
    (
        "Gala tickets (fundraising)",
        30_000,
        "fundraising",
        "City Gala",
        "2026-08-01",
        {"has_receipt": True},
    ),
    (
        "Conference hotel, after grant ends",
        41_200,
        "travel_domestic",
        "Lakeshore Hotel",
        "2027-03-01",
        {"has_receipt": True},
    ),
    ("Taxi, no receipt", 4_000, "travel_domestic", "Metro Cab", "2026-06-18", {}),
]
for label, cents, cat, merchant, day, extra in EXPENSES:
    exp = {
        "id": "e",
        "amount_cents": cents,
        "date": day,
        "merchant": merchant,
        "category": cat,
        **extra,
    }
    res = c.post(
        "/api/enforce",
        json={"expense": exp, "budget_state": budget, "ruleset_ids": [grant_id, policy_id]},
    ).json()
    dollars = f"${cents // 100:,}.{cents % 100:02d}"
    print(f"\n  {label} ({dollars})  →  {ICON[res['verdict']]}   [{res['latency_ms']} ms]")
    for t in res["traces"]:
        if t["outcome"] == "PASS":
            continue
        src = "GRANT" if t["source"] == "grant" else "YOUR POLICY"
        where = f"p.{t['citation']['page']}" if t["source"] == "grant" else "policy text"
        print(f"     {t['outcome']:<8} {src}: {t['reason']}  ({where})")
        print(f'              "{t["citation"]["quote"][:66]}"')
        print(f"              fix: {t['fix']}")
