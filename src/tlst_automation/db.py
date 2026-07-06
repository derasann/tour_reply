"""SQLite storage for reference master data only (guides/agents/tours/
stopovers/itinerary variants).

Deliberately does NOT store individual bookings: each booking's
email-derived data (guest names, dietary/medical info, etc.) lives only
in memory for the duration of one document-generation session and is
never written here. The source email/PDF continues to be kept in Google
Drive as before. This keeps the one persistent store limited to
non-customer reference data (tariff/guide/agent/tour/stopover info).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from .master import Agent, Guide, MeetingPoint, Stopover, Tour
from .models import ItineraryStop, ItineraryVariant
from .rules import tour_names_match

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

CREATE TABLE IF NOT EXISTS tour_itinerary_variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tour_name TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    itinerary TEXT DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meeting_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    en_text TEXT DEFAULT '',
    jp_text TEXT DEFAULT '',
    photo_path TEXT DEFAULT ''
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
    """Fuzzy-matched by tour name (see rules.tour_names_match): itinerary
    variants may have been saved from a guide-request PDF's own wording of
    the tour name, which doesn't always match character-for-character what
    a booking email's AI extraction produces later.
    """
    rows = conn.execute(
        "SELECT * FROM tour_itinerary_variants ORDER BY created_at DESC"
    ).fetchall()
    return [
        _row_to_itinerary_variant(row)
        for row in rows
        if tour_names_match(row["tour_name"], tour_name)
    ]


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


def upsert_meeting_point(conn: sqlite3.Connection, meeting_point: MeetingPoint) -> int:
    payload = asdict(meeting_point)
    meeting_point_id = payload.pop("id")
    if meeting_point_id is None:
        columns = ", ".join(payload.keys())
        placeholders = ", ".join(f":{k}" for k in payload.keys())
        cursor = conn.execute(
            f"INSERT OR REPLACE INTO meeting_points ({columns}) VALUES ({placeholders})", payload
        )
        conn.commit()
        return cursor.lastrowid
    assignments = ", ".join(f"{k} = :{k}" for k in payload.keys())
    payload["id"] = meeting_point_id
    conn.execute(f"UPDATE meeting_points SET {assignments} WHERE id = :id", payload)
    conn.commit()
    return meeting_point_id


def list_meeting_points(conn: sqlite3.Connection) -> list[MeetingPoint]:
    rows = conn.execute("SELECT * FROM meeting_points ORDER BY name").fetchall()
    return [MeetingPoint(**dict(row)) for row in rows]


def delete_meeting_point(conn: sqlite3.Connection, meeting_point_id: int) -> None:
    conn.execute("DELETE FROM meeting_points WHERE id = ?", (meeting_point_id,))
    conn.commit()
