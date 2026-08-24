from wg_finanztracker.ocr.donut import (
    parse_donut_result,
)


def test_parse_donut_result() -> None:
    data = {
        "menu": [
            {
                "nm": "Eisschale 1 Liter",
                "price": "1.89",
            },
            {
                "nm": "Kapseln m. Geschm.",
                "price": "1.89",
            },
        ],
        "total": {
            "total_price": "3.78",
        },
    }

    result = parse_donut_result(data)

    assert result.price_cents == 378

    assert len(result.items) == 2

    assert result.items[0].name == "Eisschale 1 Liter"

    assert result.items[0].price_cents == 189
