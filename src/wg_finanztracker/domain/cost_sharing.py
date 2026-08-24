from wg_finanztracker.domain.models import Receipt


def calculate_shares(purchase: Receipt) -> dict[int, int]:
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


def calculate_debts(purchase: Receipt) -> dict[int, int]:
    """Calculate how much each member has to pay the payer of the purchase"""
    shares = calculate_shares(purchase)
    debts: dict[int, int] = {}

    for member_id, share in shares.items():
        if member_id != purchase.paid_by.id:
            debts[member_id] = share

    return debts


def calculate_total_debts(
    purchases: list[Receipt],
) -> list[tuple[int, int, int]]:
    """
    Calculate and simplify debts across multiple purchases.
    Opposing debts are automatically offset.
    """

    balances: dict[int, int] = {}

    for purchase in purchases:
        debts = calculate_debts(purchase)
        payer_id = purchase.paid_by.id

        balances.setdefault(
            payer_id,
            0,
        )

        for debtor_id, amount in debts.items():
            balances.setdefault(
                debtor_id,
                0,
            )

            balances[debtor_id] -= amount
            balances[payer_id] += amount

    return _simplify_balances(balances)


def _simplify_balances(
    balances: dict[int, int],
) -> list[tuple[int, int, int]]:
    debtors = [
        [member_id, -balance] for member_id, balance in balances.items() if balance < 0
    ]

    creditors = [
        [member_id, balance] for member_id, balance in balances.items() if balance > 0
    ]

    debts: list[tuple[int, int, int]] = []

    debtor_index = 0
    creditor_index = 0

    while debtor_index < len(debtors) and creditor_index < len(creditors):
        debtor_id = debtors[debtor_index][0]
        debtor_amount = debtors[debtor_index][1]
        creditor_id = creditors[creditor_index][0]
        creditor_amount = creditors[creditor_index][1]

        amount = min(
            debtor_amount,
            creditor_amount,
        )

        debts.append(
            (
                debtor_id,
                creditor_id,
                amount,
            )
        )

        debtors[debtor_index][1] -= amount
        creditors[creditor_index][1] -= amount

        if debtors[debtor_index][1] == 0:
            debtor_index += 1

        if creditors[creditor_index][1] == 0:
            creditor_index += 1

    return debts
