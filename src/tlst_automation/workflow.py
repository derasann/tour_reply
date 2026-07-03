from __future__ import annotations

from datetime import date, datetime, time

from .models import BookingRequest


def build_calendar_event_payload(booking: BookingRequest) -> dict[str, object]:
    """Build a Google Calendar-style event payload without writing to Calendar."""
    start = _combine_date_time(booking.tour_date, booking.start_time)
    end = _combine_date_time(booking.tour_date, booking.end_time)
    description_lines = [
        f"Agent: {booking.agent or '-'}",
        f"Ref: {booking.ref_no or '-'}",
        f"Tour type: {booking.tour_type}",
        f"Pax: {booking.pax}",
        f"Participants: {_participants_text(booking)}",
        f"Dietary: {booking.dietary or '-'}",
        f"Medical: {booking.medical or '-'}",
        f"Amount: {booking.amount_formula or booking.amount or '-'}",
        f"Notes: {booking.notes or '-'}",
    ]
    return {
        "summary": _calendar_summary(booking),
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "description": "\n".join(description_lines),
    }


def build_tour_sheet_row(booking: BookingRequest) -> dict[str, object]:
    """Build the row data for the existing shared tour-management sheet."""
    return {
        "tour_date": booking.tour_date,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "tour_name": booking.tour_name,
        "agent": booking.agent,
        "agent_type": booking.agent_type,
        "ref_no": booking.ref_no,
        "tour_type": booking.tour_type,
        "pax": booking.pax,
        "participants": _participants_text(booking),
        "dietary": booking.dietary,
        "medical": booking.medical,
        "notes": booking.notes,
        "amount": booking.amount,
        "amount_formula": booking.amount_formula,
    }


def build_guide_calendar_entry(booking: BookingRequest) -> dict[str, object]:
    """Build a guide-assignment calendar entry for a month-tab spreadsheet."""
    return {
        "sheet_name": _guide_sheet_name(booking.tour_date),
        "tour_date": booking.tour_date,
        "day": _day_number(booking.tour_date),
        "display_text": _guide_display_text(booking),
        "tour_name": booking.tour_name,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "pax": booking.pax,
        "agent": booking.agent,
        "ref_no": booking.ref_no,
        "guide": "",
        "status": "unassigned",
    }


def _calendar_summary(booking: BookingRequest) -> str:
    prefix = {
        "AGT": "AGT",
        "EXO": "EXO",
        "BTOC": "BtoC",
    }.get(booking.agent_type.upper(), booking.agent_type)
    ref = f" #{booking.ref_no}" if booking.ref_no else ""
    return f"{booking.start_time} {prefix} {booking.tour_name} {booking.pax}pax{ref}".strip()


def _guide_display_text(booking: BookingRequest) -> str:
    time_part = f"{booking.start_time} " if booking.start_time else ""
    ref_part = f" #{booking.ref_no}" if booking.ref_no else ""
    return f"{time_part}{booking.tour_name} / {booking.pax}名{ref_part}".strip()


def _participants_text(booking: BookingRequest) -> str:
    return ", ".join(
        f"{participant.name} ({participant.age})" if participant.age else participant.name
        for participant in booking.participants
    )


def _guide_sheet_name(raw_date: str) -> str:
    parsed = _parse_iso_date(raw_date)
    if not parsed:
        return ""
    return f"{parsed.year}_{parsed.month:02d}"


def _day_number(raw_date: str) -> int | None:
    parsed = _parse_iso_date(raw_date)
    return parsed.day if parsed else None


def _combine_date_time(raw_date: str, raw_time: str) -> datetime:
    parsed_date = _parse_iso_date(raw_date) or date.today()
    parsed_time = _parse_time(raw_time) or time(0, 0)
    return datetime.combine(parsed_date, parsed_time)


def _parse_iso_date(raw_date: str) -> date | None:
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return None


def _parse_time(raw_time: str) -> time | None:
    cleaned = raw_time.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            continue
    return None
