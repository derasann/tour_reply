from tlst_automation.extractor import extract_booking_request


def test_extracts_insidejapan_booking_from_compacted_gmail_pdf_text() -> None:
    email_body = """Hello Tohoku Local Tours team, I hope you are well.
I have a new booking request for you, details as below:
**********************InsideJapan Tours Ref#: 0000001 Service Title: Hungry Samurai: Sendai Food & Culture Tour (2 - 4 people (Group experience))Day and date: Thursday 25 June 2026Start and End Times: 10:00 - 16:00Client names / Ages: Mrs Jane Ann Sample (56), Miss Amy Beth Sample (16)
Dietary requirements: Amy - mild allergy to nuts, mainly peanuts & almonds. Gets a slight rash but no swelling.Medical: Jane has asthma but carries an inhaler
Payment: Please send an invoice to InsideJapan Tours."""

    booking = extract_booking_request(email_body)

    assert booking.ref_no == "0000001"
    assert booking.tour_date == "2026-06-25"
    assert booking.tour_name == "Hungry Samurai: Sendai Food & Culture Tour"
    assert booking.start_time == "10:00"
    assert booking.end_time == "16:00"
    assert booking.pax == 2
    assert booking.participants[0].name == "Mrs Jane Ann Sample"
    assert booking.participants[1].age == 16
    assert booking.dietary.startswith("Amy - mild allergy")
    assert booking.medical == "Jane has asthma but carries an inhaler"
    assert booking.amount == 66000
