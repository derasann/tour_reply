from __future__ import annotations

from dataclasses import asdict, dataclass, field

TBA = "TBA"
TBD = "TBD"


@dataclass(frozen=True)
class Participant:
    name: str
    age: int | None = None


@dataclass(frozen=True)
class ItineraryStop:
    """One row of the guide-request itinerary table."""

    time_label: str = ""
    stopover_name: str = ""
    payment_label: str = ""
    payment_method: str = ""
    stopover_info: str = ""


@dataclass(frozen=True)
class ChecklistItem:
    label: str
    done: bool = False


@dataclass(frozen=True)
class ItineraryVariant:
    """A named, saved copy of a tour's itinerary. A tour can have several
    (e.g. the usual plan plus a taxi-based variant), so picking one up for
    a new booking never silently overwrites another."""

    id: int | None
    tour_name: str
    label: str
    itinerary: list[ItineraryStop] = field(default_factory=list)
    created_at: str = ""


@dataclass(frozen=True)
class GuideRequestStyleVariant:
    """A named, saved layout fix (cell fill/border/column-width/row-height,
    no customer content) for the guide-request PPTX's itinerary table. A
    tour can have several (e.g. bar-hopping's weekday vs weekend/holiday
    plan each needing their own touched-up layout), picked from rather
    than a single latest-wins override."""

    id: int | None
    tour_name: str
    label: str
    style_diff: dict = field(default_factory=dict)
    created_at: str = ""


@dataclass(frozen=True)
class SalesLine:
    """One row of the internal sheet's 支払内訳 (payment breakdown) table."""

    label: str
    amount: int | None = None


@dataclass(frozen=True)
class TourFeedback:
    guest_country_area: str = ""
    guest_country_name: str = ""
    guest_attribute: str = ""
    guest_pax: int | None = None
    pre_itinerary: str = ""
    post_itinerary: str = ""
    visit_count: int | None = None
    stay_duration: str = ""
    stay_reason: str = ""
    interests: str = ""
    notes: str = ""


@dataclass(frozen=True)
class BookingRequest:
    tour_date: str
    tour_name: str
    pax: int
    participants: list[Participant] = field(default_factory=list)
    agent: str = ""
    agent_type: str = "AGT"
    ref_no: str = ""
    tour_type: str = "G"
    language: str = "EN"
    dietary: str = ""
    medical: str = ""
    notes: str = ""
    start_time: str = ""
    end_time: str = ""
    amount: int | None = None
    amount_formula: str = ""

    # --- fields added for the tour-portal document generation (Booking
    # Confirmation / guide request / internal sheet) ---
    booking_no: str = ""
    status: str = ""
    payment_status: str = ""
    assignee_1st: str = ""
    assignee_2nd: str = ""
    inquiry_date: str = ""
    agent_contact: str = ""
    notes_handover: str = ""

    guide_name: str = TBA
    guide_name_romaji: str = ""  # romaji form for the (English) Booking Confirmation; falls back to guide_name if blank
    guide_mobile: str = TBD
    guide_fee: int | None = None  # final total written to documents (base + adjustment)
    guide_fee_auto_calc: bool = True  # Miyagi-departure fee formula; off for Aomori/Yamagata etc.
    guide_fee_shop_arrangement_bonus: bool = False  # bar-hopping only: guide books the shops (+1,000)
    guide_fee_adjustment: int = 0  # manual tweak (e.g. extra time for a hotel pickup)
    guide_fee_breakdown: str = ""  # e.g. "3時間 × 2,000円 = 6,000円 / 調整 +2,000円 / 合計 8,000円", shown on the guide request
    guide_request_style_id: int | None = None  # chosen saved PPTX layout (see GuideRequestStyleVariant) -- routing only, not written to any document
    emergency_contact: str = TBD

    meeting_point_name: str = ""  # selected MeetingPoint master entry, if any (for photo lookup)
    meeting_point_en: str = ""
    meeting_point_jp: str = ""
    inclusions: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)

    itinerary: list[ItineraryStop] = field(default_factory=list)
    checklist_pre: list[ChecklistItem] = field(default_factory=list)
    checklist_during: list[ChecklistItem] = field(default_factory=list)
    checklist_post: list[ChecklistItem] = field(default_factory=list)

    insurance_amount: int | None = None
    sales_lines: list[SalesLine] = field(default_factory=list)

    feedback: TourFeedback | None = None

    def to_dict(self) -> dict[str, object]:
        """Full round-trippable serialization (see from_dict) -- used for the
        one-slot local "draft" save in the new-registration page, so an
        in-progress booking survives a closed browser tab without needing a
        persistent bookings database (see db.py's module docstring)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "BookingRequest":
        data = dict(data)
        data["participants"] = [Participant(**p) for p in data.get("participants") or []]
        data["itinerary"] = [ItineraryStop(**s) for s in data.get("itinerary") or []]
        data["checklist_pre"] = [ChecklistItem(**c) for c in data.get("checklist_pre") or []]
        data["checklist_during"] = [ChecklistItem(**c) for c in data.get("checklist_during") or []]
        data["checklist_post"] = [ChecklistItem(**c) for c in data.get("checklist_post") or []]
        data["sales_lines"] = [SalesLine(**s) for s in data.get("sales_lines") or []]
        feedback = data.get("feedback")
        data["feedback"] = TourFeedback(**feedback) if feedback else None
        return cls(**data)

    def to_sheet_row_payload(self) -> dict[str, object]:
        return {
            "tour_date": self.tour_date,
            "tour_name": self.tour_name,
            "pax": self.pax,
            "participants": [
                {"name": participant.name, "age": participant.age}
                for participant in self.participants
            ],
            "agent": self.agent,
            "agent_type": self.agent_type,
            "ref_no": self.ref_no,
            "tour_type": self.tour_type,
            "language": self.language,
            "dietary": self.dietary,
            "medical": self.medical,
            "amount": self.amount,
            "amount_formula": self.amount_formula,
            "notes": self.notes,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
