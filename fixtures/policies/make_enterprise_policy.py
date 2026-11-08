"""Generate fixtures/policies/northwind_te_policy.pdf, a fictional large-organisation
travel, expense and procurement policy with the messiness real ones have:
tiered approvals, exceptions, vague wording, per-night limits, and prose that
isn't a rule. Run: python fixtures/policies/make_enterprise_policy.py (needs reportlab)
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).with_name("northwind_te_policy.pdf")

PAGES: list[list[tuple[str, str]]] = [
    [
        ("Title", "Northwind University"),
        ("Heading2", "Travel, Expense and Procurement Policy (FIN-204, rev. 7)"),
        ("BodyText", "This document is fictional and provided for demonstration only."),
        ("Heading3", "1. Purpose and Scope"),
        (
            "BodyText",
            "This policy applies to all faculty, staff, students and contractors who spend "
            "University funds, including funds from sponsored research awards. Where a sponsored "
            "award is more restrictive than this policy, the award terms take precedence.",
        ),
        (
            "BodyText",
            "Budget holders are responsible for ensuring that every expense is necessary for "
            "University business and properly documented.",
        ),
    ],
    [
        ("Heading3", "2. Approvals"),
        ("BodyText", "Expenses of $1,000 or more need manager approval."),
        ("BodyText", "Expenses of $10,000 or more need department director approval."),
        ("BodyText", "Expenses of $50,000 or more need CFO approval."),
        ("BodyText", "Gifts over $100 require the provost's approval."),
        ("BodyText", "Software subscriptions require IT approval."),
        ("Heading3", "3. Procurement"),
        ("BodyText", "Do not purchase from Amazon Marketplace."),
        (
            "BodyText",
            "Purchases of $25,000 or more must be competitively bid through Procurement Services.",
        ),
    ],
    [
        ("Heading3", "4. Travel"),
        ("BodyText", "First class airfare is not allowed unless the flight exceeds six hours."),
        ("BodyText", "Hotel rates should be reasonable and customary for the location."),
        ("BodyText", "Hotels up to $350 per night in New York, Boston and San Francisco."),
        ("BodyText", "Rideshare and taxi fares up to $100 per ride."),
        (
            "BodyText",
            "Travelers should book through the University travel portal whenever possible.",
        ),
    ],
    [
        ("Heading3", "5. Meals and Entertainment"),
        ("BodyText", "Meals up to $75 per person."),
        (
            "BodyText",
            "Alcohol is not reimbursable except at approved client entertainment events.",
        ),
        ("BodyText", "Client entertainment must be modest and directly related to business."),
    ],
    [
        ("Heading3", "6. Documentation"),
        ("BodyText", "Receipts are required for any expense of $25 or more."),
        ("BodyText", "Expense reports must be submitted within 30 days of the expense."),
        (
            "BodyText",
            "Violations of this policy may result in denial of reimbursement and disciplinary "
            "action.",
        ),
    ],
]


def main() -> None:
    styles = getSampleStyleSheet()
    story: list[object] = []
    for i, page in enumerate(PAGES):
        for style, text in page:
            story.append(Paragraph(text, styles[style]))
            story.append(Spacer(1, 8))
        if i < len(PAGES) - 1:
            story.append(PageBreak())
    SimpleDocTemplate(str(OUT), pagesize=LETTER, title="Northwind University FIN-204").build(story)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
