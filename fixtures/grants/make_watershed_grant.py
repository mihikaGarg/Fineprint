"""Generate fixtures/grants/watershed_grant.pdf, a second fictional award agreement.

A different funder and wording from the demo grant, for trying uploads: an
equipment approval at $5,000, a foreign-travel rule, banned gifts, a vague
"reasonable" clause and a budget with a participant-support line. Run:

    python fixtures/grants/make_watershed_grant.py   (needs reportlab)
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).with_name("watershed_grant.pdf")

PAGES: list[list[tuple[str, str]]] = [
    [
        ("Title", "Riverbend Watershed Monitoring Grant"),
        ("Heading2", "Grant Agreement No. RWF-2026-031"),
        (
            "BodyText",
            "This Grant Agreement is made between the Riverbend Water Fund (the Fund) and the "
            "Eastside Community Science Lab (the Grantee). This document is fictional and "
            "provided for demonstration only.",
        ),
        (
            "BodyText",
            "The Grantee will use the grant to run a two-season water quality monitoring program "
            "with high school volunteers along the lower Riverbend watershed.",
        ),
        ("Heading3", "Section 1. Grant Period"),
        (
            "BodyText",
            "The grant period begins on March 1, 2026 and ends on February 28, 2027.",
        ),
        (
            "BodyText",
            "Expenses incurred before the start of the grant period will not be reimbursed.",
        ),
    ],
    [
        ("Heading3", "Section 2. Use of Funds"),
        (
            "BodyText",
            "2.1 Grant funds may be used only for costs that are reasonable and directly related "
            "to the monitoring program.",
        ),
        (
            "BodyText",
            "2.2 Grant funds may not be used for alcoholic beverages, gifts, or entertainment.",
        ),
        ("BodyText", "2.3 Political campaign contributions are unallowable."),
        (
            "BodyText",
            "2.4 Domestic travel for field sampling is allowable within the approved budget.",
        ),
        (
            "BodyText",
            "2.5 Foreign travel requires the prior written approval of the Fund's program officer.",
        ),
        ("Heading3", "Section 3. Equipment"),
        (
            "BodyText",
            "3.1 Equipment purchases may not exceed the amount shown in the approved budget.",
        ),
        (
            "BodyText",
            "3.2 Any single piece of equipment costing $5,000 or more requires the prior written "
            "approval of the program officer.",
        ),
    ],
    [
        ("Heading3", "Section 4. Participants"),
        (
            "BodyText",
            "4.1 Stipends and travel for student volunteers must be paid from the participant "
            "support line and may not be moved to other budget lines.",
        ),
        ("Heading3", "Section 5. Reporting"),
        (
            "BodyText",
            "The Grantee shall submit an interim report by September 30, 2026 and a final report "
            "within 60 days after the end of the grant period.",
        ),
        (
            "BodyText",
            "Unspent funds shall be returned to the Fund within 90 days after the final report.",
        ),
        ("Heading3", "Signatures"),
        ("BodyText", "Riverbend Water Fund / Eastside Community Science Lab"),
    ],
    [
        ("Heading3", "Attachment A. Approved Budget"),
        ("BodyText", "The approved budget for the grant period is as follows."),
        ("BodyText", "Personnel: $48,000"),
        ("BodyText", "Domestic travel: $6,000"),
        ("BodyText", "Equipment: $15,000"),
        ("BodyText", "Supplies: $4,500"),
        ("BodyText", "Participant support: $9,000"),
        ("BodyText", "Total direct costs: $82,500"),
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
    SimpleDocTemplate(
        str(OUT), pagesize=LETTER, title="Riverbend Watershed Monitoring Grant"
    ).build(story)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
