from tlst_automation.models import BookingRequest, Participant
from tlst_automation.reply import render_reply


def test_english_reply_contains_booking_and_amount_details() -> None:
    booking = BookingRequest(
        tour_date="2026-06-25",
        tour_name="Hungry Samurai: Sendai Food & Culture Tour",
        pax=2,
        participants=[
            Participant("Mrs Jane Ann Sample", 56),
            Participant("Miss Amy Beth Sample", 16),
        ],
        agent="InsideJapan Tours",
        ref_no="0000001",
        dietary="Amy - mild allergy to nuts",
        medical="Jane has asthma and carries an inhaler",
        start_time="10:00",
        end_time="16:00",
        amount=66000,
        amount_formula="(30000 × 2) × 1.1 = 66000",
    )

    reply = render_reply(booking, contact_name="Sample Contact")

    assert "Dear Sample Contact-san" in reply
    assert "InsideJapan Tours Ref#: 0000001" in reply
    assert "Amy - mild allergy to nuts" in reply
    assert "(30000 × 2) × 1.1 = 66000 yen" in reply
