from tlst_automation.models import BookingRequest, Participant
from tlst_automation.workflow import (
    build_calendar_event_payload,
    build_guide_calendar_entry,
    build_tour_sheet_row,
)


def _booking() -> BookingRequest:
    return BookingRequest(
        tour_date="2026-10-11",
        tour_name="Back-alley Bar Hopping in Sendai",
        pax=2,
        participants=[
            Participant("Mr John Manning", 68),
            Participant("Ms Samantha Manning", 56),
        ],
        agent="InsideJapan Tours",
        agent_type="AGT",
        ref_no="1267586",
        tour_type="PV",
        dietary="Mr Manning does not eat butter or cream",
        start_time="18:00",
        end_time="20:30",
        amount=54000,
        amount_formula="(20000 × 2) × 1.1 = 44000 + 10000 = 54000",
    )


def test_build_calendar_event_payload() -> None:
    payload = build_calendar_event_payload(_booking())

    assert payload["summary"] == (
        "18:00 AGT Back-alley Bar Hopping in Sendai 2pax #1267586"
    )
    assert payload["start"]["dateTime"] == "2026-10-11T18:00:00"
    assert payload["end"]["dateTime"] == "2026-10-11T20:30:00"
    assert "Mr Manning does not eat butter or cream" in payload["description"]


def test_build_tour_sheet_row() -> None:
    row = build_tour_sheet_row(_booking())

    assert row["tour_date"] == "2026-10-11"
    assert row["tour_type"] == "PV"
    assert row["amount"] == 54000
    assert "Samantha" in row["participants"]


def test_build_guide_calendar_entry() -> None:
    entry = build_guide_calendar_entry(_booking())

    assert entry["sheet_name"] == "2026_10"
    assert entry["day"] == 11
    assert entry["status"] == "unassigned"
    assert entry["display_text"] == (
        "18:00 Back-alley Bar Hopping in Sendai / 2名 #1267586"
    )
