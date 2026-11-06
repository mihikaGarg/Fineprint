from enum import StrEnum


class ExpenseCategory(StrEnum):
    """Shared cost taxonomy used by both rules and expenses.

    Loosely follows standard federal budget object classes plus commonly
    unallowable categories. Rules and expenses must use the same values,
    so extend this enum rather than inventing strings.
    """

    PERSONNEL = "personnel"
    FRINGE = "fringe"
    TRAVEL_DOMESTIC = "travel_domestic"
    TRAVEL_FOREIGN = "travel_foreign"
    EQUIPMENT = "equipment"
    SUPPLIES = "supplies"
    CONTRACTUAL = "contractual"
    PARTICIPANT_SUPPORT = "participant_support"
    MEALS = "meals"
    ALCOHOL = "alcohol"
    ENTERTAINMENT = "entertainment"
    LOBBYING = "lobbying"
    FUNDRAISING = "fundraising"
    OTHER = "other"
