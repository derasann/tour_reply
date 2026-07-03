"""SQLite storage for bookings and master data (guides/agents/tours/stopovers).

A single-file database is enough for the "self + a few internal staff" scale
this portal targets. Nested structures (participants, itinerary rows,
checklists, sales lines, feedback) are stored as JSON text columns and
rebuilt into dataclasses on read.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .master import Agent, Guide, Stopover, Tour
from .models import (
    BookingRequest,
    ChecklistItem,
    ItineraryStop,
    ItineraryVariant,
    Participant,
    SalesLine,
    TourFeedback,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "tours.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS guides (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_romaji TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    mobile TEXT DEFAULT '',
    email TEXT DEFAULT '',
    area TEXT DEFAULT '',
    default_fee INTEGER,
    active_tours TEXT DEFAULT '[]',
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    agent_type TEXT DEFAULT 'AGT',
    contact_person TEXT DEFAULT '',
    email TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    address TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS tours (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    area TEXT DEFAULT '',
    category TEXT DEFAULT '',
    default_stopover_count INTEGER,
    meeting_point_en TEXT DEFAULT '',
    meeting_point_jp TEXT DEFAULT '',
    inclusions TEXT DEFAULT '[]',
    exclusions TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS stopovers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    unit_price INTEGER,
    category TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_no TEXT DEFAULT '',
    tour_date TEXT DEFAULT '',
    tour_name TEXT DEFAULT '',
    pax INTEGER DEFAULT 0,
    participants TEXT DEFAULT '[]',
    agent TEXT DEFAULT '',
    agent_type TEXT DEFAULT 'AGT',
    ref_no TEXT DEFAULT '',
    tour_type TEXT DEFAULT 'G',
    language TEXT DEFAULT 'EN',
    dietary TEXT DEFAULT '',
    medical TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    start_time TEXT DEFAULT '',
    end_time TEXT DEFAULT '',
    amount INTEGER,
    amount_formula TEXT DEFAULT '',
    status TEXT DEFAULT '',
    payment_status TEXT DEFAULT '',
    assignee_1st TEXT DEFAULT '',
    assignee_2nd TEXT DEFAULT '',
    inquiry_date TEXT DEFAULT '',
    agent_contact TEXT DEFAULT '',
    notes_handover TEXT DEFAULT '',
    guide_name TEXT DEFAULT 'TBA',
    guide_mobile TEXT DEFAULT 'TBD',
    guide_fee INTEGER,
    guide_fee_auto_calc INTEGER DEFAULT 1,
    guide_fee_shop_arrangement_bonus INTEGER DEFAULT 0,
    guide_fee_adjustment INTEGER DEFAULT 0,
    emergency_contact TEXT DEFAULT 'TBD',
    meeting_point_en TEXT DEFAULT '',
    meeting_point_jp TEXT DEFAULT '',
    inclusions TEXT DEFAULT '[]',
    exclusions TEXT DEFAULT '[]',
    itinerary TEXT DEFAULT '[]',
    checklist_pre TEXT DEFAULT '[]',
    checklist_during TEXT DEFAULT '[]',
    checklist_post TEXT DEFAULT '[]',
    insurance_amount INTEGER,
    sales_lines TEXT DEFAULT '[]',
    feedback TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generated_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL REFERENCES bookings(id),
    doc_type TEXT NOT NULL,
    xlsx_path TEXT,
    pptx_path TEXT,
    pdf_path TEXT,
    version INTEGER DEFAULT 1,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tour_itinerary_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tour_name TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    itinerary TEXT DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Streamlit reruns a page's script on a fresh thread from its pool, but
    # st.cache_resource keeps this connection alive process-wide across
    # those reruns -- so it inevitably gets used from more than one thread.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


# --- Booking <-> row conversion -------------------------------------------------

def booking_to_row(booking: BookingRequest) -> dict[str, object]:
    return {
        "booking_no": booking.booking_no,
        "tour_date": booking.tour_date,
        "tour_name": booking.tour_name,
        "pax": booking.pax,
        "participants": json.dumps([asdict(p) for p in booking.participants]),
        "agent": booking.agent,
        "agent_type": booking.agent_type,
        "ref_no": booking.ref_no,
        "tour_type": booking.tour_type,
        "language": booking.language,
        "dietary": booking.dietary,
        "medical": booking.medical,
        "notes": booking.notes,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "amount": booking.amount,
        "amount_formula": booking.amount_formula,
        "status": booking.status,
        "payment_status": booking.payment_status,
        "assignee_1st": booking.assignee_1st,
        "assignee_2nd": booking.assignee_2nd,
        "inquiry_date": booking.inquiry_date,
        "agent_contact": booking.agent_contact,
        "notes_handover": booking.notes_handover,
        "guide_name": booking.guide_name,
        "guide_mobile": booking.guide_mobile,
        "guide_fee": booking.guide_fee,
        "guide_fee_auto_calc": int(booking.guide_fee_auto_calc),
        "guide_fee_shop_arrangement_bonus": int(booking.guide_fee_shop_arrangement_bonus),
        "guide_fee_adjustment": booking.guide_fee_adjustment,
        "emergency_contact": booking.emergency_contact,
        "meeting_point_en": booking.meeting_point_en,
        "meeting_point_jp": booking.meeting_point_jp,
        "inclusions": json.dumps(booking.inclusions),
        "exclusions": json.dumps(booking.exclusions),
        "itinerary": json.dumps([asdict(row) for row in booking.itinerary]),
        "checklist_pre": json.dumps([asdict(row) for row in booking.checklist_pre]),
        "checklist_during": json.dumps([asdict(row) for row in booking.checklist_during]),
        "checklist_post": json.dumps([asdict(row) for row in booking.checklist_post]),
        "insurance_amount": booking.insurance_amount,
        "sales_lines": json.dumps([asdict(row) for row in booking.sales_lines]),
        "feedback": json.dumps(asdict(booking.feedback)) if booking.feedback else None,
    }


def row_to_booking(row: sqlite3.Row) -> BookingRequest:
    feedback_raw = row["feedback"]
    return BookingRequest(
        tour_date=row["tour_date"],
        tour_name=row["tour_name"],
        pax=row["pax"],
        participants=[Participant(**p) for p in json.loads(row["participants"])],
        agent=row["agent"],
        agent_type=row["agent_type"],
        ref_no=row["ref_no"],
        tour_type=row["tour_type"],
        language=row["language"],
        dietary=row["dietary"],
        medical=row["medical"],
        notes=row["notes"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        amount=row["amount"],
        amount_formula=row["amount_formula"],
        booking_no=row["booking_no"],
        status=row["status"],
        payment_status=row["payment_status"],
        assignee_1st=row["assignee_1st"],
        assignee_2nd=row["assignee_2nd"],
        inquiry_date=row["inquiry_date"],
        agent_contact=row["agent_contact"],
        notes_handover=row["notes_handover"],
        guide_name=row["guide_name"],
        guide_mobile=row["guide_mobile"],
        guide_fee=row["guide_fee"],
        guide_fee_auto_calc=bool(row["guide_fee_auto_calc"]),
        guide_fee_shop_arrangement_bonus=bool(row["guide_fee_shop_arrangement_bonus"]),
        guide_fee_adjustment=row["guide_fee_adjustment"],
        emergency_contact=row["emergency_contact"],
        meeting_point_en=row["meeting_point_en"],
        meeting_point_jp=row["meeting_point_jp"],
        inclusions=json.loads(row["inclusions"]),
        exclusions=json.loads(row["exclusions"]),
        itinerary=[ItineraryStop(**r) for r in json.loads(row["itinerary"])],
        checklist_pre=[ChecklistItem(**r) for r in json.loads(row["checklist_pre"])],
        checklist_during=[ChecklistItem(**r) for r in json.loads(row["checklist_during"])],
        checklist_post=[ChecklistItem(**r) for r in json.loads(row["checklist_post"])],
        insurance_amount=row["insurance_amount"],
        sales_lines=[SalesLine(**r) for r in json.loads(row["sales_lines"])],
        feedback=TourFeedback(**json.loads(feedback_raw)) if feedback_raw else None,
    )


def insert_booking(conn: sqlite3.Connection, booking: BookingRequest) -> int:
    row = booking_to_row(booking)
    columns = ", ".join(row.keys())
    placeholders = ", ".join(f":{key}" for key in row.keys())
    cursor = conn.execute(
        f"INSERT INTO bookings ({columns}) VALUES ({placeholders})", row
    )
    conn.commit()
    return cursor.lastrowid


def update_booking(conn: sqlite3.Connection, booking_id: int, booking: BookingRequest) -> None:
    row = booking_to_row(booking)
    assignments = ", ".join(f"{key} = :{key}" for key in row.keys())
    row["id"] = booking_id
    conn.execute(
        f"UPDATE bookings SET {assignments}, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = :id",
        row,
    )
    conn.commit()


def get_booking(conn: sqlite3.Connection, booking_id: int) -> BookingRequest | None:
    row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    return row_to_booking(row) if row else None


def list_bookings(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, booking_no, tour_name, tour_date, pax, status, payment_status, "
        "agent, guide_name FROM bookings ORDER BY tour_date DESC"
    ).fetchall()


def record_generated_document(
    conn: sqlite3.Connection,
    booking_id: int,
    doc_type: str,
    xlsx_path: str | None = None,
    pptx_path: str | None = None,
    pdf_path: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO generated_documents (booking_id, doc_type, xlsx_path, pptx_path, pdf_path) "
        "VALUES (?, ?, ?, ?, ?)",
        (booking_id, doc_type, xlsx_path, pptx_path, pdf_path),
    )
    conn.commit()
    return cursor.lastrowid


def latest_generated_documents(conn: sqlite3.Connection, booking_id: int) -> dict[str, sqlite3.Row]:
    """Most recent row per doc_type for a booking (e.g. for re-showing downloads)."""
    rows = conn.execute(
        "SELECT * FROM generated_documents WHERE booking_id = ? ORDER BY generated_at DESC",
        (booking_id,),
    ).fetchall()
    latest: dict[str, sqlite3.Row] = {}
    for row in rows:
        latest.setdefault(row["doc_type"], row)
    return latest


# --- Per-tour itinerary variants (for guide-request auto-fill) ---------------
# A tour can have several saved itinerary copies (the usual plan, a taxi
# variant, etc). Looking a tour up by name returns all of them so staff can
# pick a starting point rather than always getting one silently-overwritten
# template.

def _row_to_itinerary_variant(row: sqlite3.Row) -> ItineraryVariant:
    return ItineraryVariant(
        id=row["id"],
        tour_name=row["tour_name"],
        label=row["label"],
        itinerary=[ItineraryStop(**item) for item in json.loads(row["itinerary"])],
        created_at=row["created_at"],
    )


def list_tour_itinerary_variants(conn: sqlite3.Connection, tour_name: str) -> list[ItineraryVariant]:
    rows = conn.execute(
        "SELECT * FROM tour_itinerary_variants WHERE tour_name = ? ORDER BY created_at DESC",
        (tour_name,),
    ).fetchall()
    return [_row_to_itinerary_variant(row) for row in rows]


def save_tour_itinerary_variant(
    conn: sqlite3.Connection, tour_name: str, label: str, stops: list[ItineraryStop]
) -> int:
    payload = json.dumps([asdict(stop) for stop in stops])
    cursor = conn.execute(
        "INSERT INTO tour_itinerary_variants (tour_name, label, itinerary) VALUES (?, ?, ?)",
        (tour_name, label, payload),
    )
    conn.commit()
    return cursor.lastrowid


def update_tour_itinerary_variant(
    conn: sqlite3.Connection, variant_id: int, label: str, stops: list[ItineraryStop]
) -> None:
    payload = json.dumps([asdict(stop) for stop in stops])
    conn.execute(
        "UPDATE tour_itinerary_variants SET label = ?, itinerary = ? WHERE id = ?",
        (label, payload, variant_id),
    )
    conn.commit()


def delete_tour_itinerary_variant(conn: sqlite3.Connection, variant_id: int) -> None:
    conn.execute("DELETE FROM tour_itinerary_variants WHERE id = ?", (variant_id,))
    conn.commit()


def list_tour_itinerary_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT tour_name FROM tour_itinerary_variants ORDER BY tour_name"
    ).fetchall()
    return [row["tour_name"] for row in rows]


# --- Master data CRUD (thin helpers; Streamlit master pages call these) --------

def upsert_guide(conn: sqlite3.Connection, guide: Guide) -> int:
    payload = {**asdict(guide), "active_tours": json.dumps(guide.active_tours)}
    guide_id = payload.pop("id")
    if guide_id is None:
        columns = ", ".join(payload.keys())
        placeholders = ", ".join(f":{k}" for k in payload.keys())
        cursor = conn.execute(f"INSERT INTO guides ({columns}) VALUES ({placeholders})", payload)
        conn.commit()
        return cursor.lastrowid
    assignments = ", ".join(f"{k} = :{k}" for k in payload.keys())
    payload["id"] = guide_id
    conn.execute(f"UPDATE guides SET {assignments} WHERE id = :id", payload)
    conn.commit()
    return guide_id


def list_guides(conn: sqlite3.Connection) -> list[Guide]:
    rows = conn.execute("SELECT * FROM guides ORDER BY name").fetchall()
    return [
        Guide(
            id=row["id"],
            name=row["name"],
            name_romaji=row["name_romaji"],
            phone=row["phone"],
            mobile=row["mobile"],
            email=row["email"],
            area=row["area"],
            default_fee=row["default_fee"],
            active_tours=json.loads(row["active_tours"]),
            notes=row["notes"],
        )
        for row in rows
    ]


def upsert_agent(conn: sqlite3.Connection, agent: Agent) -> int:
    payload = asdict(agent)
    agent_id = payload.pop("id")
    if agent_id is None:
        columns = ", ".join(payload.keys())
        placeholders = ", ".join(f":{k}" for k in payload.keys())
        cursor = conn.execute(f"INSERT INTO agents ({columns}) VALUES ({placeholders})", payload)
        conn.commit()
        return cursor.lastrowid
    assignments = ", ".join(f"{k} = :{k}" for k in payload.keys())
    payload["id"] = agent_id
    conn.execute(f"UPDATE agents SET {assignments} WHERE id = :id", payload)
    conn.commit()
    return agent_id


def list_agents(conn: sqlite3.Connection) -> list[Agent]:
    rows = conn.execute("SELECT * FROM agents ORDER BY company_name").fetchall()
    return [Agent(**dict(row)) for row in rows]


def upsert_tour(conn: sqlite3.Connection, tour: Tour) -> int:
    payload = {
        **asdict(tour),
        "inclusions": json.dumps(tour.inclusions),
        "exclusions": json.dumps(tour.exclusions),
    }
    tour_id = payload.pop("id")
    if tour_id is None:
        columns = ", ".join(payload.keys())
        placeholders = ", ".join(f":{k}" for k in payload.keys())
        cursor = conn.execute(
            f"INSERT OR REPLACE INTO tours ({columns}) VALUES ({placeholders})", payload
        )
        conn.commit()
        return cursor.lastrowid
    assignments = ", ".join(f"{k} = :{k}" for k in payload.keys())
    payload["id"] = tour_id
    conn.execute(f"UPDATE tours SET {assignments} WHERE id = :id", payload)
    conn.commit()
    return tour_id


def list_tours(conn: sqlite3.Connection) -> list[Tour]:
    rows = conn.execute("SELECT * FROM tours ORDER BY name").fetchall()
    return [
        Tour(
            id=row["id"],
            name=row["name"],
            area=row["area"],
            category=row["category"],
            default_stopover_count=row["default_stopover_count"],
            meeting_point_en=row["meeting_point_en"],
            meeting_point_jp=row["meeting_point_jp"],
            inclusions=json.loads(row["inclusions"]),
            exclusions=json.loads(row["exclusions"]),
        )
        for row in rows
    ]


def upsert_stopover(conn: sqlite3.Connection, stopover: Stopover) -> int:
    payload = asdict(stopover)
    stopover_id = payload.pop("id")
    if stopover_id is None:
        columns = ", ".join(payload.keys())
        placeholders = ", ".join(f":{k}" for k in payload.keys())
        cursor = conn.execute(
            f"INSERT INTO stopovers ({columns}) VALUES ({placeholders})", payload
        )
        conn.commit()
        return cursor.lastrowid
    assignments = ", ".join(f"{k} = :{k}" for k in payload.keys())
    payload["id"] = stopover_id
    conn.execute(f"UPDATE stopovers SET {assignments} WHERE id = :id", payload)
    conn.commit()
    return stopover_id


def list_stopovers(conn: sqlite3.Connection) -> list[Stopover]:
    rows = conn.execute("SELECT * FROM stopovers ORDER BY name").fetchall()
    return [Stopover(**dict(row)) for row in rows]


def delete_guide(conn: sqlite3.Connection, guide_id: int) -> None:
    conn.execute("DELETE FROM guides WHERE id = ?", (guide_id,))
    conn.commit()


def delete_agent(conn: sqlite3.Connection, agent_id: int) -> None:
    conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    conn.commit()


def delete_tour(conn: sqlite3.Connection, tour_id: int) -> None:
    conn.execute("DELETE FROM tours WHERE id = ?", (tour_id,))
    conn.commit()


def delete_stopover(conn: sqlite3.Connection, stopover_id: int) -> None:
    conn.execute("DELETE FROM stopovers WHERE id = ?", (stopover_id,))
    conn.commit()
