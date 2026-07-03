from tlst_automation.pdf_masker import mask_text


def test_masks_email_phone_and_titled_names() -> None:
    text = (
        "To: Mrs Jane Ann Sample (56) <jane@example.com>\n"
        "Phone: +81(0)70-0000-0000\n"
        "サンプル様"
    )

    masked = mask_text(text, strength=3)

    assert "jane@example.com" not in masked
    assert "+81(0)70-0000-0000" not in masked
    assert "Jane" not in masked
    assert "Ann" not in masked
    assert "サンプル様" not in masked
    assert "Mrs." in masked


def test_masks_exo_split_titles_and_booking_name() -> None:
    text = (
        "New Booking Request | TKE0000000 / SAMPLE Alex & Sam / 06-Nov & 07-Nov-2026\n"
        "予約名Booking Name SAMPLE Alex & Sam\n"
        "予約部BookingDepartment English 3\n"
        "お客様名Pax name(s) M rs Alex Jordan SAMPLE (Adult) "
        "M r Sam SAMPLE (Adult)"
    )

    masked = mask_text(text, strength=3)

    assert "SAMPLE Alex & Sam" not in masked
    assert "Alex" not in masked
    assert "Jordan" not in masked
    assert "Sam" not in masked
    assert "M rs" not in masked
    assert "M r" not in masked
    assert "Mrs." in masked
    assert "Mr." in masked
