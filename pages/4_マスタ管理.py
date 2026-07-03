"""マスタ管理: ガイド・依頼元・ツアー・立ち寄り先単価を表形式で編集する。

各セクションの表を直接編集し（行の追加・削除も表の操作で可能）、
「保存」ボタンで反映する。次回以降の書類生成・行程表の自動反映に使われる。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portal_common import get_conn, require_login  # noqa: E402
from tlst_automation import db  # noqa: E402
from tlst_automation.master import Agent, Guide, Stopover, Tour  # noqa: E402

st.set_page_config(page_title="マスタ管理 - ツアー予約割当ポータル", layout="wide")
require_login()
conn = get_conn()

st.title("マスタ管理")
st.caption("表を直接編集してください。行の追加は表の一番下、削除は行を選んで Delete キー（またはゴミ箱アイコン）でできます。")


def _split_list(text: str) -> list[str]:
    return [line.strip() for line in text.split(";") if line.strip()]


def _join_list(items: list[str]) -> str:
    return "; ".join(items)


# --- ガイド ---------------------------------------------------------------
st.header("ガイド")
guides = db.list_guides(conn)
guides_df = pd.DataFrame(
    [
        {
            "id": g.id, "name": g.name, "name_romaji": g.name_romaji, "phone": g.phone,
            "mobile": g.mobile, "email": g.email, "area": g.area,
            "default_fee": g.default_fee, "active_tours": _join_list(g.active_tours), "notes": g.notes,
        }
        for g in guides
    ],
    columns=["id", "name", "name_romaji", "phone", "mobile", "email", "area", "default_fee", "active_tours", "notes"],
)
edited_guides = st.data_editor(
    guides_df,
    num_rows="dynamic",
    use_container_width=True,
    key="guides_editor",
    column_config={"id": st.column_config.NumberColumn("id", disabled=True)},
)
if st.button("ガイドを保存", type="primary", key="save_guides"):
    kept_ids = set()
    for row in edited_guides.to_dict("records"):
        if not str(row.get("name") or "").strip():
            continue
        row_id = int(row["id"]) if pd.notna(row.get("id")) else None
        new_id = db.upsert_guide(
            conn,
            Guide(
                id=row_id,
                name=row.get("name") or "",
                name_romaji=row.get("name_romaji") or "",
                phone=row.get("phone") or "",
                mobile=row.get("mobile") or "",
                email=row.get("email") or "",
                area=row.get("area") or "",
                default_fee=int(row["default_fee"]) if pd.notna(row.get("default_fee")) else None,
                active_tours=_split_list(str(row.get("active_tours") or "")),
                notes=row.get("notes") or "",
            ),
        )
        kept_ids.add(row_id or new_id)
    for guide in guides:
        if guide.id not in kept_ids:
            db.delete_guide(conn, guide.id)
    st.success("ガイド情報を保存しました。")
    st.rerun()

st.divider()

# --- 依頼元 ---------------------------------------------------------------
st.header("依頼元（旅行会社・OTA）")
agents = db.list_agents(conn)
agents_df = pd.DataFrame(
    [
        {
            "id": a.id, "company_name": a.company_name, "agent_type": a.agent_type,
            "contact_person": a.contact_person, "email": a.email, "phone": a.phone, "address": a.address,
        }
        for a in agents
    ],
    columns=["id", "company_name", "agent_type", "contact_person", "email", "phone", "address"],
)
edited_agents = st.data_editor(
    agents_df,
    num_rows="dynamic",
    use_container_width=True,
    key="agents_editor",
    column_config={
        "id": st.column_config.NumberColumn("id", disabled=True),
        "agent_type": st.column_config.SelectboxColumn("agent_type", options=["AGT", "EXO", "BtoC"]),
    },
)
if st.button("依頼元を保存", type="primary", key="save_agents"):
    kept_ids = set()
    for row in edited_agents.to_dict("records"):
        if not str(row.get("company_name") or "").strip():
            continue
        row_id = int(row["id"]) if pd.notna(row.get("id")) else None
        new_id = db.upsert_agent(
            conn,
            Agent(
                id=row_id,
                company_name=row.get("company_name") or "",
                agent_type=row.get("agent_type") or "AGT",
                contact_person=row.get("contact_person") or "",
                email=row.get("email") or "",
                phone=row.get("phone") or "",
                address=row.get("address") or "",
            ),
        )
        kept_ids.add(row_id or new_id)
    for agent in agents:
        if agent.id not in kept_ids:
            db.delete_agent(conn, agent.id)
    st.success("依頼元情報を保存しました。")
    st.rerun()

st.divider()

# --- ツアー ---------------------------------------------------------------
st.header("ツアー")
tours = db.list_tours(conn)
tours_df = pd.DataFrame(
    [
        {
            "id": t.id, "name": t.name, "area": t.area, "category": t.category,
            "meeting_point_en": t.meeting_point_en, "meeting_point_jp": t.meeting_point_jp,
            "inclusions": _join_list(t.inclusions), "exclusions": _join_list(t.exclusions),
        }
        for t in tours
    ],
    columns=["id", "name", "area", "category", "meeting_point_en", "meeting_point_jp", "inclusions", "exclusions"],
)
edited_tours = st.data_editor(
    tours_df,
    num_rows="dynamic",
    use_container_width=True,
    key="tours_editor",
    column_config={
        "id": st.column_config.NumberColumn("id", disabled=True),
        "category": st.column_config.SelectboxColumn("category", options=["bar_hop", "food", "sightseeing", "other"]),
        "inclusions": st.column_config.TextColumn("inclusions（;区切り）"),
        "exclusions": st.column_config.TextColumn("exclusions（;区切り）"),
    },
)
if st.button("ツアーを保存", type="primary", key="save_tours"):
    kept_ids = set()
    for row in edited_tours.to_dict("records"):
        if not str(row.get("name") or "").strip():
            continue
        row_id = int(row["id"]) if pd.notna(row.get("id")) else None
        new_id = db.upsert_tour(
            conn,
            Tour(
                id=row_id,
                name=row.get("name") or "",
                area=row.get("area") or "",
                category=row.get("category") or "",
                meeting_point_en=row.get("meeting_point_en") or "",
                meeting_point_jp=row.get("meeting_point_jp") or "",
                inclusions=_split_list(str(row.get("inclusions") or "")),
                exclusions=_split_list(str(row.get("exclusions") or "")),
            ),
        )
        kept_ids.add(row_id or new_id)
    for tour in tours:
        if tour.id not in kept_ids:
            db.delete_tour(conn, tour.id)
    st.success("ツアー情報を保存しました。")
    st.rerun()

st.divider()

# --- 立ち寄り先単価 ---------------------------------------------------------
st.header("立ち寄り先単価")
stopovers = db.list_stopovers(conn)
stopovers_df = pd.DataFrame(
    [
        {
            "id": s.id, "name": s.name, "address": s.address, "phone": s.phone,
            "unit_price": s.unit_price, "category": s.category, "notes": s.notes,
        }
        for s in stopovers
    ],
    columns=["id", "name", "address", "phone", "unit_price", "category", "notes"],
)
edited_stopovers = st.data_editor(
    stopovers_df,
    num_rows="dynamic",
    use_container_width=True,
    key="stopovers_editor",
    column_config={"id": st.column_config.NumberColumn("id", disabled=True)},
)
if st.button("立ち寄り先単価を保存", type="primary", key="save_stopovers"):
    kept_ids = set()
    for row in edited_stopovers.to_dict("records"):
        if not str(row.get("name") or "").strip():
            continue
        row_id = int(row["id"]) if pd.notna(row.get("id")) else None
        new_id = db.upsert_stopover(
            conn,
            Stopover(
                id=row_id,
                name=row.get("name") or "",
                address=row.get("address") or "",
                phone=row.get("phone") or "",
                unit_price=int(row["unit_price"]) if pd.notna(row.get("unit_price")) else None,
                category=row.get("category") or "",
                notes=row.get("notes") or "",
            ),
        )
        kept_ids.add(row_id or new_id)
    for stopover in stopovers:
        if stopover.id not in kept_ids:
            db.delete_stopover(conn, stopover.id)
    st.success("立ち寄り先単価を保存しました（値上げなどの反映は次回以降の書類生成から適用されます）。")
    st.rerun()
