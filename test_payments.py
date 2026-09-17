def test_payment_amount():

    amount = 1000

    assert amount > 0


def test_payment_method():

    methods = [
        "Cash",
        "UPI",
        "Card",
        "Bank Transfer"
    ]

    assert "UPI" in methods


def test_payment_date():

    payment_date = "2026-09-16"

    assert payment_date != ""