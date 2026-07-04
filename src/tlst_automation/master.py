"""Master-data dataclasses: guides, agents, tours, stopovers.

These mirror the reference tables already kept by hand in Sheet2 of
0625Hungry.xlsx (area / tour name / guide / agent company) and in
KNOWLEDGE.md (guide contact list, tariff unit prices). Storage/CRUD lives
in db.py; this module only defines the shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Guide:
    id: int | None
    name: str
    name_romaji: str = ""
    phone: str = ""
    mobile: str = ""
    email: str = ""
    area: str = ""
    default_fee: int | None = None
    active_tours: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class Agent:
    id: int | None
    company_name: str
    agent_type: str = "AGT"  # AGT / EXO / BtoC
    contact_person: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""


@dataclass(frozen=True)
class Tour:
    id: int | None
    name: str
    area: str = ""
    category: str = ""  # e.g. bar_hop / food / other
    default_stopover_count: int | None = None
    meeting_point_en: str = ""
    meeting_point_jp: str = ""
    inclusions: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Stopover:
    id: int | None
    name: str
    address: str = ""
    phone: str = ""
    unit_price: int | None = None
    category: str = ""
    notes: str = ""


@dataclass(frozen=True)
class MeetingPoint:
    """A reusable named meeting point (e.g. "JR Sendai Station 2F"), shared
    across tours/bookings rather than retyped each time. `photo_path` is a
    local file path to the photo pasted into the Booking Confirmation.
    """

    id: int | None
    name: str
    en_text: str = ""
    jp_text: str = ""
    photo_path: str = ""
