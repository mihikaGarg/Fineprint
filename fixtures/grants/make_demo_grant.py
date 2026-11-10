"""Generate fixtures/grants/demo_grant.pdf, an illustrative (fictional) award agreement.

Some rules use standard wording the keyword finder catches; others are phrased
differently so only the LLM proposer finds them. Run:

    python fixtures/grants/make_demo_grant.py   (needs reportlab)
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).with_name("demo_grant.pdf")

PAGES: list[list[tuple[str, str]]] = [
    [
        ("Title", "Community Climate Research Award"),
        ("Heading2", "Award Agreement No. CCR-2026-014"),
        (
            "BodyText",
            "This Award Agreement is entered into between the Northfield Climate "
            "Foundation (the Foundation) and Lakeview Research Collaborative (the "
            "Recipient). This document is fictional and provided for demonstration only.",
        ),
        (
            "BodyText",
            "The Recipient shall use award funds solely for the project described in the "
            "approved proposal and in accordance with the cost principles of 2 CFR Part 200, "
            "except where this Agreement states otherwise.",
        ),
        ("Heading3", "Article 1. Definitions"),
        (
            "BodyText",
            "Program Officer means the Foundation staff member named in the notice of award. "
            "Approved budget means the budget attached to this Agreement as Exhibit B, "
            "as amended in writing.",
        ),
    ],
    [
        ("Heading3", "Article 2. Term"),
        (
            "BodyText",
            "The period of performance for this award begins on February 1, 2026 and ends on "
            "January 31, 2027.",
        ),
        (
            "BodyText",
            "Costs incurred outside the period of performance may not be charged to the award "
            "unless the Foundation agrees in writing.",
        ),
        ("Heading3", "Article 3. Payments"),
        (
            "BodyText",
            "The Foundation will pay the award in quarterly installments following receipt of "
            "an acceptable financial report. The Recipient shall return any unexpended funds "
            "within 90 days after the end of the award.",
        ),
        ("Heading3", "Article 4. Budget Revisions"),
        (
            "BodyText",
            "The Recipient may move up to ten percent of the total award between budget "
            "categories without approval. Larger changes require a written amendment.",
        ),
    ],
    [
        ("Heading3", "Article 5. Allowable and Unallowable Costs"),
        (
            "BodyText",
            "5.1 Domestic travel necessary to carry out the project is allowable within the "
            "approved budget.",
        ),
        (
            "BodyText",
            "5.2 The Recipient may not charge the award for alcoholic beverages, entertainment, "
            "or lobbying activities of any kind.",
        ),
        ("BodyText", "5.3 Fundraising costs are unallowable."),
        (
            "BodyText",
            "5.4 Meals are allowable only when they are an integral part of a project meeting "
            "and are reasonable in cost.",
        ),
    ],
    [
        ("Heading3", "Article 7. Equipment"),
        (
            "BodyText",
            "7.1 Equipment expenditures may not exceed the amount shown in the approved budget.",
        ),
        (
            "BodyText",
            "7.2 Any single item of equipment costing $10,000 or more must receive the Program "
            "Officer's written approval before purchase.",
        ),
        ("Heading3", "Article 8. Reporting"),
        (
            "BodyText",
            "The Recipient shall submit a financial report within 30 days after the end of each "
            "quarter and a final report within 90 days after the end of the award.",
        ),
        ("Heading3", "Signatures"),
        ("BodyText", "Northfield Climate Foundation / Lakeview Research Collaborative"),
    ],
    [
        ("Heading3", "Exhibit B. Approved Budget"),
        ("BodyText", "The approved budget for the period of performance is as follows."),
        ("BodyText", "Personnel: $62,000"),
        ("BodyText", "Domestic travel: $8,000"),
        ("BodyText", "Equipment: $20,000"),
        ("BodyText", "Supplies: $6,500"),
        ("BodyText", "Total direct costs: $96,500"),
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
    SimpleDocTemplate(str(OUT), pagesize=LETTER, title="Community Climate Research Award").build(
        story
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
