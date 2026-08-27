from collections import defaultdict

from wg_finanztracker.domain.cost_sharing import calculate_shares
from wg_finanztracker.domain.models import Receipt

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Lebensmittel": (
        "milch",
        "brot",
        "pizza",
        "nudel",
        "kaese",
        "käse",
        "cola",
        "wasser",
        "obst",
        "gemuese",
        "gemüse",
        "joghurt",
    ),
    "Haushalt": (
        "toilettenpapier",
        "spuelmittel",
        "spülmittel",
        "müllbeutel",
        "muellbeutel",
        "reiniger",
        "waschmittel",
        "küchenrolle",
        "kuechenrolle",
        "schwamm",
    ),
    "Hygiene": (
        "shampoo",
        "duschgel",
        "zahnpasta",
        "seife",
        "deo",
        "rasierer",
        "hygiene",
    ),
    "Getränke": (
        "bier",
        "wein",
        "saft",
        "energy",
        "tee",
        "kaffee",
    ),
}


def categorize_item_name(name: str) -> str:
    """Categorize an item based on keywords in its name"""
    normalized = name.casefold()

    for category, keywords in _CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in normalized:
                return category

    return "Sonstiges"


def calculate_category_totals(
    receipts: list[Receipt],
) -> dict[str, int]:
    """Calculate the total amount spent in each category"""
    totals: dict[str, int] = defaultdict(int)

    for receipt in receipts:
        for item in receipt.items:
            category = categorize_item_name(item.name)
            totals[category] += item.price_cents

    return dict(
        sorted(
            totals.items(),
            key=lambda entry: entry[1],
            reverse=True,
        )
    )


def calculate_member_spending_totals(
    receipts: list[Receipt],
) -> dict[int, int]:
    """Calculate the total amount assigned to each member"""
    totals: dict[int, int] = defaultdict(int)

    for receipt in receipts:
        shares = calculate_shares(receipt)

        for member_id, amount_cents in shares.items():
            totals[member_id] += amount_cents

    return dict(
        sorted(
            totals.items(),
            key=lambda entry: entry[1],
            reverse=True,
        )
    )


def calculate_monthly_totals(
    receipts: list[Receipt],
) -> list[tuple[int, int, int]]:
    """Calculate the total amount spent in each month"""
    totals: dict[tuple[int, int], int] = defaultdict(int)

    for receipt in receipts:
        key = (
            receipt.purchase_date.year,
            receipt.purchase_date.month,
        )
        totals[key] += receipt.price_cents

    result = [
        (year, month, amount_cents) for (year, month), amount_cents in totals.items()
    ]

    result.sort(
        key=lambda entry: (
            entry[0],
            entry[1],
        )
    )

    return result


def calculate_yearly_totals(
    receipts: list[Receipt],
) -> list[tuple[int, int]]:
    """Calculate total spending grouped by year"""
    totals: dict[int, int] = defaultdict(int)

    for receipt in receipts:
        totals[receipt.purchase_date.year] += receipt.price_cents

    return sorted(totals.items(), key=lambda entry: entry[0])
