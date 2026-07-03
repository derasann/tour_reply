from __future__ import annotations

import re
from datetime import datetime

from .models import BookingRequest, Participant
from .pricing import price_booking

FIELD_LABELS = [
    "InsideJapan Tours Ref#",
    "Ref#",
    "Service Title",
    "Day and date",
    "Start and End Times",
    "Client names / Ages",
    "Dietary requirements",
    "Medical",
    "Payment",
    "Emergency contact",
    "IJT note",
]


def extract_booking_request(email_body: str) -> BookingRequest:
    """Extract a booking request from a structured agent email.

    This is intentionally conservative. It handles common InsideJapan-style
    emails first, and leaves uncertain fields blank for review.
    """
    ref_no = _field_value(email_body, "Ref#")
    tour_name = _field_value(email_body, "Service Title")
    tour_name = _clean_service_title(tour_name)
    tour_date = _parse_date(_field_value(email_body, "Day and date"))
    start_time, end_time = _parse_time_range(
        _field_value(email_body, "Start and End Times")
    )
    participants = _extract_participants(email_body)
    dietary = _field_value(email_body, "Dietary requirements")
    medical = _field_value(email_body, "Medical")

    booking = BookingRequest(
        tour_date=tour_date,
        tour_name=tour_name,
        pax=len(participants),
        participants=participants,
        agent="InsideJapan Tours" if "InsideJapan" in email_body else "",
        agent_type="AGT",
        ref_no=ref_no,
        tour_type="G",
        language="EN",
        dietary=dietary,
        medical=medical,
        start_time=start_time,
        end_time=end_time,
    )
    return price_booking(booking)


def _match(text: str, pattern: str) -> str:
    matched = re.search(pattern, text, flags=re.IGNORECASE)
    return matched.group(1).strip() if matched else ""


def _field_value(text: str, label: str) -> str:
    next_labels = [candidate for candidate in FIELD_LABELS if candidate != label]
    next_label_pattern = "|".join(re.escape(candidate) for candidate in next_labels)
    pattern = rf"{re.escape(label)}:\s*(.*?)(?=(?:{next_label_pattern}):|\*{{4,}}|$)"
    matches = list(re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL))
    if not matches:
        return ""
    # Gmail PDFs often contain our reply first and the original request later.
    # The last structured field is usually the source request we want to parse.
    return _normalize_space(matches[-1].group(1))


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clean_service_title(value: str) -> str:
    value = re.sub(
        r"\s*\(\s*\d+\s*-\s*\d+\s*people\s*\(\s*Group experience\s*\)\s*\)\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip()


def _parse_date(raw_date: str) -> str:
    if not raw_date:
        return ""
    cleaned = raw_date.strip()
    for date_format in ("%A %d %B %Y", "%A, %d %B %Y", "%d %B %Y"):
        try:
            return datetime.strptime(cleaned, date_format).date().isoformat()
        except ValueError:
            continue
    return cleaned


def _parse_time_range(raw_time: str) -> tuple[str, str]:
    if not raw_time:
        return "", ""
    parts = re.split(r"\s*[-–]\s*", raw_time.strip(), maxsplit=1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return raw_time.strip(), ""


def _extract_participants(email_body: str) -> list[Participant]:
    block = _field_value(email_body, "Client names / Ages")
    participants: list[Participant] = []
    participant_matches = re.findall(
        r"((?:Mr|Mrs|Ms|Miss|Dr)\.?\s+.*?\(\d{1,3}\))",
        block,
        flags=re.IGNORECASE,
    )
    chunks = participant_matches or re.split(r"\s*,\s*", block)
    for chunk in chunks:
        cleaned = chunk.strip().strip(",")
        if not cleaned:
            continue
        matched = re.match(r"(.+?)\s*\((\d{1,3})\)", cleaned)
        if matched:
            participants.append(Participant(matched.group(1).strip(), int(matched.group(2))))
        else:
            participants.append(Participant(cleaned))
    return participants


def _extract_section(text: str, start_label: str, end_label: str) -> str:
    pattern = rf"{re.escape(start_label)}:\s*(.*?)(?:\n\s*{re.escape(end_label)}:|\Z)"
    matched = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not matched:
        return ""
    return " ".join(line.strip() for line in matched.group(1).splitlines() if line.strip())
