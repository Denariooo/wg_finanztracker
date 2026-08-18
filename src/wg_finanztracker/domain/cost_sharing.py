from wg_finanztracker.domain.models import Purchase


def calculate_shares(purchase: Purchase) -> dict[int, int]:
    """Calculate each members share of a purchase"""
    shares: dict[int, int] = {}

    for item in purchase.items:
        if not item.assigned_to:
            raise ValueError(f"Item '{item.name}' has no assigned members")

        member_count = len(item.assigned_to)
        base_share = item.price_cents // member_count
        remainder = item.price_cents % member_count

        for index, member in enumerate(item.assigned_to):
            share = base_share

            if index < remainder:
                share += 1

            if member.id not in shares:
                shares[member.id] = 0

            shares[member.id] += share

    return shares


def calculate_debts(purchase: Purchase) -> dict[int, int]:
    """Calculate how much each member has to pay the payer of the purchase"""
    shares = calculate_shares(purchase)
    debts: dict[int, int] = {}

    for member_id, share in shares.items():
        if member_id != purchase.paid_by.id:
            debts[member_id] = share

    return debts
