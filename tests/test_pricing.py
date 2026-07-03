from tlst_automation.pricing import calculate_amount


def test_agt_price_uses_tax_exclusive_unit_price() -> None:
    amount, formula = calculate_amount(
        "Hungry Samurai: Sendai Food & Culture Tour",
        2,
        agent_type="AGT",
        tour_type="G",
    )

    assert amount == 66000
    assert formula == "(30000 × 2) × 1.1 = 66000"


def test_private_surcharge_is_added_for_non_exo_private_tour() -> None:
    amount, formula = calculate_amount(
        "Back-alley Bar Hopping in Sendai",
        2,
        agent_type="AGT",
        tour_type="PV",
    )

    assert amount == 54000
    assert formula.endswith("+ 10000 = 54000")


def test_exo_price_uses_gross_unit_price_without_private_surcharge() -> None:
    amount, formula = calculate_amount(
        "Sendai Bar Hopping Tour",
        2,
        agent_type="EXO",
        tour_type="PV",
    )

    assert amount == 51920
    assert formula == "25960 × 2 = 51920"


def test_attracxi_price_uses_slide_rate() -> None:
    amount, formula = calculate_amount(
        "Attracxi: Mysteries of the Three Holy Mountains of Dewa",
        3,
        agent_type="AGT",
        tour_type="G",
    )

    assert amount == 247500
    assert formula == "82500 × 3 = 247500"


def test_attracxi_price_uses_five_plus_slide_rate() -> None:
    amount, formula = calculate_amount(
        "Attracxi: Hiraizumi Full Day Tour from Sendai",
        5,
        agent_type="AGT",
        tour_type="G",
    )

    assert amount == 302500
    assert formula == "60500 × 5 = 302500"


def test_exo_dewa_sanzan_uses_slide_rate() -> None:
    amount, formula = calculate_amount(
        "The Sacred Peaks of Yamagata Day Trip from Sendai",
        2,
        agent_type="EXO",
        tour_type="G",
    )

    assert amount == 198000
    assert formula == "99000 × 2 = 198000"
