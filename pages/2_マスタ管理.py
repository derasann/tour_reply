"""マスタ管理: ガイド・依頼元・ツアー・立ち寄り先単価を表形式で編集する。

各セクションの表を直接編集し（行の追加・削除も表の操作で可能）、
「保存」ボタンで反映する。次回以降の書類生成・行程表の自動反映に使われる。
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portal_common import get_conn, save_meeting_point_photo  # noqa: E402
from tlst_automation import db  # noqa: E402
from tlst_automation.ai_extractor import (  # noqa: E402
    ExtractionError,
    extract_confirmation_document,
    extract_guide_request_document,
)
from tlst_automation.master import Agent, Guide, MeetingPoint, Stopover, Tour  # noqa: E402
from tlst_automation.models import ItineraryStop  # noqa: E402

st.set_page_config(page_title="マスタ管理 - ツアー予約割当ポータル", layout="wide")
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
    width="stretch",
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
    width="stretch",
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
    width="stretch",
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
    width="stretch",
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

st.divider()

# --- 集合場所 ---------------------------------------------------------------
st.header("集合場所")
st.caption("Booking Confirmationの「集合場所」プルダウンから選べます。写真を登録すると確認書に反映されます。")
meeting_points = db.list_meeting_points(conn)
meeting_points_df = pd.DataFrame(
    [
        {"id": mp.id, "name": mp.name, "en_text": mp.en_text, "jp_text": mp.jp_text, "写真": bool(mp.photo_path)}
        for mp in meeting_points
    ],
    columns=["id", "name", "en_text", "jp_text", "写真"],
)
edited_meeting_points = st.data_editor(
    meeting_points_df,
    num_rows="dynamic",
    width="stretch",
    key="meeting_points_editor",
    column_config={
        "id": st.column_config.NumberColumn("id", disabled=True),
        "写真": st.column_config.CheckboxColumn("写真", disabled=True),
    },
)
if st.button("集合場所を保存", type="primary", key="save_meeting_points"):
    kept_ids = set()
    for row in edited_meeting_points.to_dict("records"):
        if not str(row.get("name") or "").strip():
            continue
        row_id = int(row["id"]) if pd.notna(row.get("id")) else None
        existing = next((mp for mp in meeting_points if mp.id == row_id), None)
        new_id = db.upsert_meeting_point(
            conn,
            MeetingPoint(
                id=row_id,
                name=row.get("name") or "",
                en_text=row.get("en_text") or "",
                jp_text=row.get("jp_text") or "",
                photo_path=existing.photo_path if existing else "",
            ),
        )
        kept_ids.add(row_id or new_id)
    for meeting_point in meeting_points:
        if meeting_point.id not in kept_ids:
            db.delete_meeting_point(conn, meeting_point.id)
    st.success("集合場所を保存しました。")
    st.rerun()

st.subheader("写真の登録・差し替え")
meeting_points = db.list_meeting_points(conn)
if not meeting_points:
    st.caption("集合場所がまだ登録されていません。上の表で追加してください。")
else:
    photo_target_name = st.selectbox(
        "集合場所を選択", [mp.name for mp in meeting_points], key="mp_photo_target"
    )
    photo_target = next(mp for mp in meeting_points if mp.name == photo_target_name)
    if photo_target.photo_path and Path(photo_target.photo_path).exists():
        st.image(photo_target.photo_path, width=300, caption="現在登録されている写真")
    else:
        st.caption("この集合場所にはまだ写真がありません。")
    uploaded_mp_photo = st.file_uploader(
        "写真をアップロード（差し替え）", type=["png", "jpg", "jpeg"], key="mp_photo_upload"
    )
    if uploaded_mp_photo is not None and st.button("この写真を保存", key="save_mp_photo"):
        photo_path = save_meeting_point_photo(uploaded_mp_photo.getvalue(), photo_target.id)
        db.upsert_meeting_point(
            conn,
            MeetingPoint(
                id=photo_target.id, name=photo_target.name,
                en_text=photo_target.en_text, jp_text=photo_target.jp_text, photo_path=photo_path,
            ),
        )
        st.success("写真を保存しました。")
        st.rerun()

st.divider()

# --- 過去のBooking Confirmationからの取込 -------------------------------------
st.header("過去のBooking Confirmationから集合場所・Inclusions/Exclusionsを取り込む")
st.caption(
    "作成済みのBooking Confirmation（PDF）をドラッグ＆ドロップすると、AIがツアー名・集合場所・"
    "Inclusions/Exclusionsを読み取ります。埋め込まれている写真も取り込み候補として表示します。"
)
uploaded_confirmation_pdf = st.file_uploader(
    "Booking Confirmation PDFをドラッグ＆ドロップ", type=["pdf"], key="import_confirmation_pdf"
)

if uploaded_confirmation_pdf is not None:
    upload_signature = (uploaded_confirmation_pdf.name, uploaded_confirmation_pdf.size)
    if st.session_state.get("_import_confirmation_signature") != upload_signature:
        st.session_state["_import_confirmation_signature"] = upload_signature
        reader = PdfReader(uploaded_confirmation_pdf)
        pdf_text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        candidate_images = sorted(
            (img.data for page in reader.pages for img in page.images),
            key=len,
            reverse=True,
        )
        st.session_state["_import_confirmation_photo"] = candidate_images[0] if candidate_images else None
        try:
            with st.spinner("AIで読み取り中..."):
                st.session_state["_import_confirmation_result"] = extract_confirmation_document(pdf_text)
        except ExtractionError as exc:
            st.error(f"読み取りに失敗しました: {exc}")
            st.session_state["_import_confirmation_result"] = None

    confirmation_extracted = st.session_state.get("_import_confirmation_result")
    if confirmation_extracted:
        st.success(f"ツアー名「{confirmation_extracted.get('tour_name', '')}」を読み取りました。")
        confirm_col1, confirm_col2 = st.columns(2)
        with confirm_col1:
            st.write("**集合場所**")
            st.text(f"EN: {confirmation_extracted.get('meeting_point_en', '')}")
            st.text(f"JP: {confirmation_extracted.get('meeting_point_jp', '')}")
            photo_bytes = st.session_state.get("_import_confirmation_photo")
            if photo_bytes:
                st.image(photo_bytes, width=250, caption="取り込み候補の写真（最大サイズの埋め込み画像）")
            else:
                st.caption("このPDFからは画像を抽出できませんでした。")
        with confirm_col2:
            st.write("**Inclusions**")
            st.write(confirmation_extracted.get("inclusions", []))
            st.write("**Exclusions**")
            st.write(confirmation_extracted.get("exclusions", []))

        import_mp_name = st.text_input(
            "保存する集合場所名", value=confirmation_extracted.get("meeting_point_en", "") or "新しい集合場所",
            key="import_mp_name",
        )
        if st.button("この集合場所として保存", type="primary", key="import_save_meeting_point"):
            new_mp_id = db.upsert_meeting_point(
                conn,
                MeetingPoint(
                    id=None, name=import_mp_name,
                    en_text=confirmation_extracted.get("meeting_point_en", ""),
                    jp_text=confirmation_extracted.get("meeting_point_jp", ""),
                ),
            )
            photo_bytes = st.session_state.get("_import_confirmation_photo")
            if photo_bytes:
                photo_path = save_meeting_point_photo(photo_bytes, new_mp_id)
                mp = next(mp for mp in db.list_meeting_points(conn) if mp.id == new_mp_id)
                db.upsert_meeting_point(conn, MeetingPoint(id=mp.id, name=mp.name, en_text=mp.en_text, jp_text=mp.jp_text, photo_path=photo_path))
            st.success(f"「{import_mp_name}」として集合場所を保存しました。")
            st.rerun()

        import_tour_name_for_incl = st.text_input(
            "Inclusions/Exclusionsを反映するツアー名",
            value=confirmation_extracted.get("tour_name", ""),
            key="import_confirmation_tour_name",
        )
        if st.button("このInclusions/Exclusionsをツアーマスタに反映", key="import_save_inclusions"):
            matched_tour = next((t for t in db.list_tours(conn) if t.name == import_tour_name_for_incl), None)
            if matched_tour is None:
                st.error(f"「{import_tour_name_for_incl}」という名前のツアーが見つかりません。ツアーマスタで先に名前を確認してください。")
            else:
                db.upsert_tour(
                    conn,
                    Tour(
                        id=matched_tour.id, name=matched_tour.name, area=matched_tour.area,
                        category=matched_tour.category, default_stopover_count=matched_tour.default_stopover_count,
                        meeting_point_en=matched_tour.meeting_point_en, meeting_point_jp=matched_tour.meeting_point_jp,
                        inclusions=confirmation_extracted.get("inclusions", []) or matched_tour.inclusions,
                        exclusions=confirmation_extracted.get("exclusions", []) or matched_tour.exclusions,
                    ),
                )
                st.success(f"「{import_tour_name_for_incl}」のInclusions/Exclusionsを更新しました。")

st.divider()

# --- 過去のガイド依頼書からの取込 ---------------------------------------------
st.header("過去のガイド依頼書から行程・単価を取り込む")
st.caption(
    "作成済みのガイド依頼書（PDF）をドラッグ＆ドロップすると、AIがツアー名と行程表を読み取ります。"
    "そのツアーの行程パターンとして保存したり、単価が明確な立ち寄り先だけ単価マスタに追加できます。"
)
uploaded_guide_pdf = st.file_uploader(
    "ガイド依頼書PDFをドラッグ＆ドロップ", type=["pdf"], key="import_guide_pdf"
)

if uploaded_guide_pdf is not None:
    upload_signature = (uploaded_guide_pdf.name, uploaded_guide_pdf.size)
    if st.session_state.get("_import_guide_pdf_signature") != upload_signature:
        st.session_state["_import_guide_pdf_signature"] = upload_signature
        reader = PdfReader(uploaded_guide_pdf)
        pdf_text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        try:
            with st.spinner("AIで読み取り中..."):
                st.session_state["_import_guide_pdf_result"] = extract_guide_request_document(pdf_text)
        except ExtractionError as exc:
            st.error(f"読み取りに失敗しました: {exc}")
            st.session_state["_import_guide_pdf_result"] = None

    extracted = st.session_state.get("_import_guide_pdf_result")
    if extracted:
        itinerary_rows = extracted.get("itinerary", [])
        st.success(f"ツアー名「{extracted.get('tour_name', '')}」、行程{len(itinerary_rows)}件を読み取りました。")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "時間": row.get("time_label", ""),
                        "立ち寄り先": row.get("stopover_name", ""),
                        "支払額": row.get("payment_label", ""),
                        "支払方法": row.get("payment_method", ""),
                        "立ち寄り先情報": row.get("stopover_info", ""),
                        "単価目安": row.get("unit_price"),
                    }
                    for row in itinerary_rows
                ]
            ),
            width="stretch",
        )

        import_tour_name = st.text_input(
            "保存先のツアー名", value=extracted.get("tour_name", ""), key="import_tour_name"
        )
        import_variant_label = st.text_input(
            "行程パターン名", value=f"PDF取込 {date.today().isoformat()}", key="import_variant_label"
        )

        import_col1, import_col2 = st.columns(2)
        with import_col1:
            if st.button("行程パターンとして保存", type="primary", key="import_save_itinerary"):
                stops = [
                    ItineraryStop(
                        time_label=row.get("time_label", ""),
                        stopover_name=row.get("stopover_name", ""),
                        payment_label=row.get("payment_label", ""),
                        payment_method=row.get("payment_method", ""),
                        stopover_info=row.get("stopover_info", ""),
                    )
                    for row in itinerary_rows
                ]
                db.save_tour_itinerary_variant(conn, import_tour_name, import_variant_label, stops)
                st.success(f"「{import_tour_name}」の行程パターンとして保存しました。")
        with import_col2:
            if st.button("単価が明確な立ち寄り先を単価マスタに追加", key="import_save_stopovers"):
                existing_names = {s.name for s in db.list_stopovers(conn)}
                added = 0
                for row in itinerary_rows:
                    name = str(row.get("stopover_name", "")).strip()
                    price = row.get("unit_price")
                    if not name or price is None or name in existing_names:
                        continue
                    db.upsert_stopover(
                        conn,
                        Stopover(id=None, name=name, address=str(row.get("stopover_info", "")), unit_price=int(price)),
                    )
                    existing_names.add(name)
                    added += 1
                st.success(f"立ち寄り先単価に{added}件追加しました（単価が明確だった項目のみ、既存と同名のものはスキップ）。")
