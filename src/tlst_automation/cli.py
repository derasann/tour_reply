from __future__ import annotations

import argparse
import json
from pathlib import Path

from .extractor import extract_booking_request
from .reply import render_reply
from .workflow import (
    build_calendar_event_payload,
    build_guide_calendar_entry,
    build_tour_sheet_row,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email_file", type=Path)
    args = parser.parse_args()

    booking = extract_booking_request(args.email_file.read_text(encoding="utf-8"))
    print(json.dumps(booking.to_sheet_row_payload(), ensure_ascii=False, indent=2))
    print("\n--- Calendar Event Payload ---\n")
    print(json.dumps(build_calendar_event_payload(booking), ensure_ascii=False, indent=2))
    print("\n--- Tour Sheet Row Payload ---\n")
    print(json.dumps(build_tour_sheet_row(booking), ensure_ascii=False, indent=2))
    print("\n--- Guide Calendar Entry Payload ---\n")
    print(json.dumps(build_guide_calendar_entry(booking), ensure_ascii=False, indent=2))
    print("\n--- Reply Draft ---\n")
    print(render_reply(booking, contact_name="Partner"))


if __name__ == "__main__":
    main()
