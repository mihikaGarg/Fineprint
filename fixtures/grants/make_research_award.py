# ruff: noqa: E501  (agreement prose)
"""Generate fixtures/grants/research_award.pdf: a full-length, fictional research award agreement.

Written in the structure and language of a real foundation award (recitals,
definitions, numbered articles, signature blocks, exhibits with a statement of
work, budget and justification) so uploads can be tried on a realistic,
wordy document. Every name, number and party is invented; the footer marks it
as a sample. Run:

    python fixtures/grants/make_research_award.py   (needs reportlab)
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).with_name("research_award.pdf")
AWARD_NO = "HF-2026-0147"

base = getSampleStyleSheet()
BODY = ParagraphStyle(
    "Body",
    parent=base["BodyText"],
    fontName="Times-Roman",
    fontSize=10.5,
    leading=14.5,
    alignment=TA_JUSTIFY,
    spaceAfter=7,
)
CLAUSE = ParagraphStyle("Clause", parent=BODY, leftIndent=18, firstLineIndent=-18)
SUB = ParagraphStyle("Sub", parent=BODY, leftIndent=36, firstLineIndent=-18)
ART = ParagraphStyle(
    "Article",
    parent=base["Heading2"],
    fontName="Times-Bold",
    fontSize=12,
    spaceBefore=12,
    spaceAfter=6,
)
EXH = ParagraphStyle(
    "Exhibit",
    parent=base["Heading1"],
    fontName="Times-Bold",
    fontSize=14,
    alignment=TA_CENTER,
    spaceAfter=10,
)
CENTER = ParagraphStyle("Center", parent=BODY, alignment=TA_CENTER)
TITLE = ParagraphStyle(
    "TitleX", parent=base["Title"], fontName="Times-Bold", fontSize=20, leading=24, spaceAfter=6
)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=9, leading=12)

story: list[object] = []


def p(text: str, style: ParagraphStyle = BODY) -> None:
    story.append(Paragraph(text, style))


def article(title: str) -> None:
    story.append(Paragraph(title, ART))


def clauses(*items: str) -> None:
    for item in items:
        story.append(Paragraph(item, CLAUSE))


def table(rows: list[list[str]], widths: list[float], money_cols: tuple[int, ...] = ()) -> None:
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("FONT", (0, 0), (-1, -1), "Times-Roman", 10),
        ("FONT", (0, 0), (-1, 0), "Times-Bold", 10),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]
    for col in money_cols:
        style.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    story.append(t)
    story.append(Spacer(1, 10))


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Times-Roman", 8.5)
    canvas.drawString(
        inch, 0.6 * inch, f"Award No. {AWARD_NO}. Sample document; all parties fictional."
    )
    canvas.drawRightString(LETTER[0] - inch, 0.6 * inch, f"Page {doc.page}")
    canvas.restoreState()


# ---------------------------------------------------------------- cover
story.append(Spacer(1, 1.2 * inch))
p("THE HALVERSON FOUNDATION FOR ENVIRONMENTAL HEALTH", CENTER)
story.append(Spacer(1, 0.3 * inch))
story.append(Paragraph("Research Award Agreement", TITLE))
p(f"Award No. {AWARD_NO}", CENTER)
story.append(Spacer(1, 0.4 * inch))
table(
    [
        ["Award detail", ""],
        ["Recipient", "Lakeshore State University, Office of Sponsored Programs"],
        [
            "Principal Investigator",
            "Dr. Amara Okafor, Department of Civil and Environmental Engineering",
        ],
        ["Project title", "Low-Cost Sensor Networks for Urban Air Quality in Schools"],
        ["Total award amount", "$263,000"],
        ["Period of performance", "July 1, 2026 through June 30, 2028"],
        ["Program Officer", "Daniel Reyes, Senior Program Officer"],
        ["Payment method", "Quarterly advance payments"],
    ],
    [1.8 * inch, 4.7 * inch],
)
story.append(Spacer(1, 0.3 * inch))
p(
    "This Research Award Agreement, together with its Exhibits, is the entire agreement between "
    "the parties for the project described below. It is a sample document prepared for software "
    "demonstration; the Foundation, the Recipient and every person named are fictional.",
    SMALL,
)
story.append(PageBreak())

# ---------------------------------------------------------------- recitals and definitions
article("Recitals")
p(
    "WHEREAS, The Halverson Foundation for Environmental Health (the Foundation) supports research "
    "that measures and reduces the exposure of children to environmental hazards; and WHEREAS, "
    "Lakeshore State University (the Recipient) submitted a proposal dated February 14, 2026 "
    "titled Low-Cost Sensor Networks for Urban Air Quality in Schools (the Proposal); and WHEREAS, "
    "the Foundation has reviewed the Proposal and wishes to support the project on the terms set "
    "out in this Agreement; NOW, THEREFORE, the parties agree as follows."
)

article("Article 1. Definitions")
p("In this Agreement the following terms have the meanings given below.")
clauses(
    "1.1 Agreement means this Research Award Agreement, including Exhibit A (Statement of Work), "
    "Exhibit B (Approved Budget and Budget Justification) and Exhibit C (Reporting Schedule), as "
    "amended in writing from time to time.",
    "1.2 Approved Budget means the budget set out in Exhibit B, as revised in accordance with "
    "Article 8.",
    "1.3 Direct Costs means costs that can be identified specifically with the project and charged "
    "to it with a high degree of accuracy.",
    "1.4 Equipment means tangible personal property having a useful life of more than one year "
    "and a per-unit acquisition cost of $5,000 or more.",
    "1.5 Participant Support Costs means stipends, subsistence allowances, travel allowances and "
    "registration fees paid to or on behalf of participants or trainees, but not employees, in "
    "connection with conferences, workshops or training activities under the project.",
    "1.6 Program Officer means the Foundation staff member identified on the cover page of this "
    "Agreement, or any successor the Foundation designates in writing.",
    "1.7 Prior written approval means approval given in writing, including by electronic mail, by "
    "the Program Officer before the cost is incurred or the action is taken.",
)

# ---------------------------------------------------------------- term and amount
article("Article 2. Period of Performance")
clauses(
    "2.1 The period of performance for this award begins on July 1, 2026 and ends on June 30, 2028.",
    "2.2 Costs incurred outside the period of performance may not be charged to the award unless "
    "the Program Officer gives prior written approval.",
    "2.3 Pre-award costs incurred up to 90 days before the start of the period of performance may "
    "be charged to the award only with the prior written approval of the Program Officer and only "
    "if they would have been allowable had they been incurred during the period of performance.",
    "2.4 The Recipient may request one no-cost extension of up to twelve months by writing to the "
    "Program Officer at least 45 days before the end of the period of performance. An extension "
    "is effective only when confirmed in a written amendment.",
)

article("Article 3. Award Amount and Payments")
clauses(
    "3.1 The Foundation will provide a total of $263,000 for the project, consisting of $242,000 "
    "in direct costs and $21,000 in indirect costs, as detailed in Exhibit B.",
    "3.2 The Foundation will pay the award in quarterly advances. The first payment will be made "
    "within 30 days after the Foundation receives this Agreement signed by the Recipient. Later "
    "payments will be made after the Foundation accepts the financial report for the preceding "
    "quarter.",
    "3.3 The Foundation is not obligated to pay any amount beyond the total award amount, and the "
    "Recipient is responsible for any costs that exceed it.",
    "3.4 Award funds must be held in an account that allows them to be identified separately from "
    "the Recipient's other funds. Interest earned on advances in excess of $500 in any fiscal year "
    "must be returned to the Foundation.",
)

# ---------------------------------------------------------------- costs
article("Article 4. Allowable Costs")
clauses(
    "4.1 Award funds may be used only for costs that are necessary for the project, reasonable in "
    "amount, consistently treated with the Recipient's other activities, adequately documented, "
    "and allocable to the project in accordance with the Approved Budget.",
    "4.2 In determining whether a cost is allowable, the Recipient shall follow the cost principles "
    "of 2 CFR Part 200, Subpart E, except where this Agreement states otherwise.",
    "4.3 Salaries and wages are allowable for the time that personnel actually spend on the project, "
    "as recorded in the Recipient's effort reporting system and certified at least every six months.",
    "4.4 Meals are allowable only when they are an integral part of a project meeting, workshop or "
    "field activity, and the cost per person may not exceed the applicable federal per diem rate for "
    "the location.",
)

article("Article 5. Unallowable Costs")
p("The following costs are unallowable and may not be charged to the award in any amount:")
clauses(
    "5.1 Alcoholic beverages are unallowable.",
    "5.2 The Recipient may not charge the award for entertainment, including tickets to shows or "
    "sporting events, social activities and any associated costs.",
    "5.3 Fundraising and investment management costs are unallowable.",
    "5.4 Lobbying costs, including any attempt to influence legislation or the outcome of an "
    "election, are unallowable.",
    "5.5 Fines, penalties and settlements resulting from a failure to comply with any law or "
    "regulation are unallowable.",
    "5.6 Gifts to any person, including gifts of cash, gift cards and promotional items, are "
    "unallowable.",
    "5.7 Memberships in social, dining or country clubs are unallowable.",
)

# ---------------------------------------------------------------- travel and equipment
article("Article 6. Travel")
clauses(
    "6.1 Domestic travel necessary to carry out the project is allowable within the Approved Budget.",
    "6.2 Air travel must be booked in economy or coach class at the lowest reasonable fare. "
    "First-class airfare is not allowed unless the traveler has a documented medical need or no "
    "other class of service is available on a reasonable schedule, and in either case the "
    "Recipient must keep the documentation with the travel record.",
    "6.3 Foreign travel requires the prior written approval of the Program Officer. Each request "
    "must state the traveler, destination, dates, purpose and estimated cost.",
    "6.4 Lodging and subsistence may not exceed the federal per diem rates in effect for the "
    "location on the date of travel, except that the Recipient may reimburse actual lodging costs "
    "up to 150 percent of the federal rate when lodging at the conference hotel.",
)

article("Article 7. Equipment and Supplies")
clauses(
    "7.1 Equipment expenditures may not exceed the amount shown in the Approved Budget.",
    "7.2 Any single item of equipment costing $10,000 or more must receive the Program Officer's "
    "written approval before purchase, even if the item is listed in the Approved Budget.",
    "7.3 Title to equipment purchased with award funds vests in the Recipient, which shall use the "
    "equipment for the project for as long as it is needed and keep an inventory record of each "
    "item, including its serial number, cost, location and condition.",
    "7.4 Items costing less than $5,000 per unit are supplies and must be charged to the Materials "
    "and Supplies line of the Approved Budget.",
)

# ---------------------------------------------------------------- budget changes etc.
article("Article 8. Budget Revisions")
clauses(
    "8.1 The Recipient may transfer funds among direct cost categories without approval, provided "
    "that the cumulative amount transferred does not exceed ten percent of the total award.",
    "8.2 Transfers that exceed the limit in Section 8.1, any change to the scope or objectives of "
    "the project, and any change of Principal Investigator require prior written approval.",
    "8.3 Funds budgeted for participant support costs may not be used for any other purpose "
    "without the prior written approval of the Program Officer.",
    "8.4 Indirect costs are limited to ten percent of modified total direct costs, which exclude "
    "equipment and participant support costs, and may not be increased by rebudgeting.",
)

article("Article 9. Subawards and Contracts")
clauses(
    "9.1 The Recipient may not make a subaward under this Agreement without the prior written "
    "approval of the Program Officer.",
    "9.2 Purchases of services under the Contractual line must follow the Recipient's written "
    "procurement procedures, and any single contract of $25,000 or more must be competitively "
    "bid unless the Program Officer approves a sole-source justification.",
)

article("Article 10. Reports")
clauses(
    "10.1 The Recipient shall submit a financial report within 30 days after the end of each "
    "calendar quarter, showing expenditures by budget category for the quarter and cumulatively.",
    "10.2 The Recipient shall submit an annual technical report within 60 days after the end of "
    "each project year, and a final technical and financial report within 90 days after the end "
    "of the period of performance.",
    "10.3 The Foundation may withhold payments while any required report is overdue.",
)

article("Article 11. Records and Audit")
clauses(
    "11.1 The Recipient shall keep financial records, supporting documents and all other records "
    "relating to this award for three years after the date the final financial report is "
    "submitted, or longer if any litigation, claim or audit is started before the end of that "
    "period.",
    "11.2 The Foundation, or auditors it designates, may examine any records of the Recipient "
    "relating to the award on reasonable notice during normal business hours.",
    "11.3 The Recipient shall repay any amount that an audit finds was charged to the award in "
    "violation of this Agreement.",
)

article("Article 12. Publications and Intellectual Property")
clauses(
    "12.1 Publications resulting from the project shall acknowledge the support of The Halverson "
    "Foundation for Environmental Health under Award No. HF-2026-0147.",
    "12.2 The Recipient owns any inventions and data it develops under the project. The Recipient "
    "grants the Foundation a non-exclusive, royalty-free license to use project data and reports "
    "for non-commercial purposes.",
    "12.3 Data collected in schools shall be shared only in de-identified form and in accordance "
    "with the data management plan in the Proposal.",
)

article("Article 13. Compliance")
clauses(
    "13.1 Research involving human participants must be approved by the Recipient's Institutional "
    "Review Board before it begins, and the Recipient shall keep the approval current for the life "
    "of the project.",
    "13.2 The Recipient certifies that neither it nor its principal employees are debarred, "
    "suspended or otherwise excluded from receiving grants from any government or foundation.",
    "13.3 The Recipient shall disclose to the Program Officer any financial conflict of interest of "
    "the Principal Investigator or project personnel within 30 days after it is identified.",
)

article("Article 14. Termination and Closeout")
clauses(
    "14.1 The Foundation may suspend or terminate this award, in whole or in part, if the Recipient "
    "materially fails to comply with this Agreement and does not correct the failure within 30 days "
    "after written notice.",
    "14.2 Either party may terminate this award for convenience on 60 days' written notice. The "
    "Foundation will pay allowable costs properly incurred before the effective date of "
    "termination and non-cancellable commitments made before notice was given.",
    "14.3 The Recipient shall return any unexpended funds within 90 days after the end of the "
    "period of performance or the effective date of termination.",
)

article("Article 15. General Provisions")
clauses(
    "15.1 This Agreement may be amended only in writing signed by authorized representatives of "
    "both parties.",
    "15.2 This Agreement is governed by the laws of the State of Illinois, without regard to its "
    "conflict of laws rules.",
    "15.3 Notices under this Agreement shall be sent to the Program Officer for the Foundation and "
    "to the Office of Sponsored Programs for the Recipient.",
)

story.append(Spacer(1, 14))
story.append(
    KeepTogether(
        [
            Paragraph("Signatures", ART),
            Paragraph(
                "IN WITNESS WHEREOF, the parties have executed this Agreement as of the dates below.",
                BODY,
            ),
            Spacer(1, 8),
            Table(
                [
                    ["THE HALVERSON FOUNDATION", "LAKESHORE STATE UNIVERSITY"],
                    ["", ""],
                    ["By: ______________________________", "By: ______________________________"],
                    [
                        "Margaret Lindqvist, Vice President for Grants",
                        "Thomas Achebe, Director, Sponsored Programs",
                    ],
                    ["Date: May 20, 2026", "Date: May 27, 2026"],
                    ["", ""],
                    ["", "Acknowledged by the Principal Investigator:"],
                    ["", "______________________________"],
                    ["", "Dr. Amara Okafor"],
                ],
                colWidths=[3.25 * inch, 3.25 * inch],
                style=TableStyle(
                    [
                        ("FONT", (0, 0), (-1, -1), "Times-Roman", 10),
                        ("FONT", (0, 0), (-1, 0), "Times-Bold", 10),
                    ]
                ),
            ),
        ]
    )
)
story.append(PageBreak())

# ---------------------------------------------------------------- Exhibit A
story.append(Paragraph("Exhibit A. Statement of Work", EXH))
p(
    "Background. Children spend roughly a third of their weekdays in school buildings, yet few "
    "schools measure the air their students breathe. Commercial monitoring stations are accurate "
    "but expensive, so data from inside classrooms is rare, especially in under-resourced districts."
)
p(
    "Objective. The project will design, install and validate a network of low-cost particulate "
    "and carbon dioxide sensors in 24 classrooms across six public schools, compare the readings "
    "with reference instruments, and give each school a plain-language dashboard and a short list "
    "of ventilation changes ranked by cost."
)
p("Aims and milestones.")
clauses(
    "Aim 1. Build and calibrate 60 sensor units against two reference monitors in the Recipient's "
    "laboratory (months 1 to 6).",
    "Aim 2. Install units in 24 classrooms and collect continuous data through two school years, "
    "with monthly maintenance visits (months 4 to 22).",
    "Aim 3. Run two summer workshops for 20 teachers and 20 high school students on reading and "
    "using the data (summers of 2027 and 2028).",
    "Aim 4. Publish the hardware design and calibration method openly and deliver a final report "
    "to each participating school (months 20 to 24).",
)
p(
    "Personnel. The Principal Investigator will devote 15 percent effort to the project. A "
    "postdoctoral researcher (100 percent effort, 24 months) will lead calibration and analysis, "
    "and two graduate research assistants (50 percent effort each) will build, install and "
    "maintain the sensor units."
)
story.append(PageBreak())

# ---------------------------------------------------------------- Exhibit B
story.append(Paragraph("Exhibit B. Approved Budget", EXH))
p("The approved budget for the full period of performance is as follows.")
table(
    [
        ["Budget category", "Amount"],
        ["Salaries and Wages", "$132,000"],
        ["Fringe Benefits", "$39,600"],
        ["Domestic Travel", "$9,800"],
        ["Foreign Travel", "$6,500"],
        ["Equipment", "$18,000"],
        ["Materials and Supplies", "$11,200"],
        ["Participant Support", "$14,000"],
        ["Contractual", "$7,500"],
        ["Other Direct Costs", "$3,400"],
        ["Total Direct Costs", "$242,000"],
        ["Indirect Costs (10% of MTDC)", "$21,000"],
        ["Total Award", "$263,000"],
    ],
    [4.2 * inch, 2.3 * inch],
    money_cols=(1,),
)
p("Budget by project year.", BODY)
table(
    [
        ["Category", "Year 1", "Year 2", "Total"],
        ["Salaries and wages", "$65,000", "$67,000", "$132,000"],
        ["Fringe benefits", "$19,500", "$20,100", "$39,600"],
        ["Domestic travel", "$4,600", "$5,200", "$9,800"],
        ["Foreign travel", "$0", "$6,500", "$6,500"],
        ["Equipment", "$18,000", "$0", "$18,000"],
        ["Materials and supplies", "$7,400", "$3,800", "$11,200"],
        ["Participant support", "$7,000", "$7,000", "$14,000"],
        ["Contractual", "$3,000", "$4,500", "$7,500"],
        ["Other direct costs", "$1,700", "$1,700", "$3,400"],
        ["Indirect costs", "$10,500", "$10,500", "$21,000"],
        ["Total", "$136,700", "$126,300", "$263,000"],
    ],
    [2.5 * inch, 1.3 * inch, 1.3 * inch, 1.4 * inch],
    money_cols=(1, 2, 3),
)

story.append(Paragraph("Budget Justification", ART))
clauses(
    "B.1 Salaries and wages. Principal Investigator at 15 percent effort for two years; one "
    "postdoctoral researcher at 100 percent effort for 24 months; two graduate research assistants "
    "at 50 percent effort during the academic year. Rates include a three percent annual increase.",
    "B.2 Fringe benefits. Calculated at the Recipient's negotiated rate of 30 percent of salaries "
    "and wages.",
    "B.3 Domestic travel. Monthly mileage for maintenance visits to the six schools and one trip "
    "per year for two people to present results at a national environmental health conference.",
    "B.4 Foreign travel. One trip for the Principal Investigator to present at an international air "
    "quality symposium in year two, subject to the prior written approval required by Section 6.3.",
    "B.5 Equipment. Two reference particulate monitors at $9,000 each, used to calibrate the "
    "low-cost units. Each monitor is below the $10,000 approval threshold in Section 7.2.",
    "B.6 Materials and supplies. Sensor components, enclosures, microcontrollers, mounting hardware "
    "and replacement filters for 60 units, at approximately $185 per unit.",
    "B.7 Participant support. Stipends of $250 per day for teachers and students attending the "
    "summer workshops, plus local travel allowances. These funds are restricted under Section 8.3.",
    "B.8 Contractual. Professional design of the school dashboards and translation of the final "
    "school reports into Spanish.",
    "B.9 Other direct costs. Cellular data plans for the sensor network and open-access "
    "publication fees.",
)
story.append(PageBreak())

# ---------------------------------------------------------------- Exhibit C
story.append(Paragraph("Exhibit C. Reporting Schedule", EXH))
table(
    [
        ["Report", "Period covered", "Due date"],
        ["Quarterly financial report", "Each calendar quarter", "30 days after quarter end"],
        ["Year 1 technical report", "July 1, 2026 to June 30, 2027", "August 29, 2027"],
        ["Year 2 technical report", "July 1, 2027 to June 30, 2028", "Combined with final report"],
        [
            "Final technical and financial report",
            "Full period of performance",
            "September 28, 2028",
        ],
        ["Equipment inventory", "Cumulative", "With final report"],
    ],
    [2.3 * inch, 2.3 * inch, 1.9 * inch],
)
p(
    "Reports shall be submitted through the Foundation's grantee portal. Questions about reporting "
    "should be directed to the Program Officer."
)

SimpleDocTemplate(
    str(OUT),
    pagesize=LETTER,
    title="Research Award Agreement HF-2026-0147",
    leftMargin=inch,
    rightMargin=inch,
    topMargin=0.9 * inch,
    bottomMargin=0.9 * inch,
).build(story, onFirstPage=footer, onLaterPages=footer)
print(f"Wrote {OUT}")
