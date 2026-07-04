"""Shared helpers for the multipage tour portal (pages/*.py).

Kept at the project root (not under src/) since it's Streamlit-app glue,
not a reusable library module.
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from tlst_automation import db  # noqa: E402
from tlst_automation.docgen.guide_request import generate_guide_request  # noqa: E402
from tlst_automation.docgen.pdf_export import (  # noqa: E402
    PdfExportError,
    convert_to_pdf,
    export_workbook_sheet_pdf,
)
from tlst_automation.docgen.tour_workbook import generate_tour_workbook  # noqa: E402
from tlst_automation.models import (  # noqa: E402
    BookingRequest,
    ChecklistItem,
    ItineraryStop,
)
from tlst_automation import rules  # noqa: E402
from tlst_automation.rules import tbd  # noqa: E402

GENERATED_DIR = Path(__file__).resolve().parent / "generated"
MEETING_POINT_PHOTOS_DIR = Path(__file__).resolve().parent / "data" / "meeting_point_photos"
ITINERARY_COLUMNS = ["時間", "立ち寄り先", "支払額", "支払方法", "立ち寄り先情報"]
CHECKLIST_LABELS = {
    "pre": ["見積提出", "コンファメーション送付", "インボイス送付"],
    "during": ["ガイド手配", "保険加入"],
    "post": ["ガイド報告", "ガイド清算シート記入確認"],
}


def ensure_api_key() -> None:
    if "ANTHROPIC_API_KEY" not in os.environ and "anthropic_api_key" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["anthropic_api_key"]


@st.cache_resource
def get_conn():
    return db.connect()


def extract_text_from_upload(uploaded_file) -> str:
    if uploaded_file.name.lower().endswith(".pdf"):
        reader = PdfReader(uploaded_file)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return uploaded_file.read().decode("utf-8", errors="replace")


_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DATE_PATTERNS = [
    re.compile(r"(?P<y>20\d{2})\s*年\s*(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日"),
    re.compile(r"(?P<y>20\d{2})[/-](?P<m>\d{1,2})[/-](?P<d>\d{1,2})"),
    re.compile(r"(?P<d>\d{1,2})\s+(?P<mon>[A-Za-z]+)\s+(?P<y>20\d{2})"),
    re.compile(r"(?P<mon>[A-Za-z]+)\s+(?P<d>\d{1,2}),?\s+(?P<y>20\d{2})"),
]


def _extract_likely_datetime(text: str) -> _dt.datetime | None:
    """Best-effort: find the email/correspondence date near the top of the
    text (Gmail PDF exports show sender + date right after the headers).
    Used only to order multiple uploaded threads chronologically before
    handing them to the AI -- not a guarantee, just a best-effort nudge
    (the AI is also told to resolve conflicts by recency; see
    ai_extractor.py).
    """
    head = text[:1500]
    for pattern in _DATE_PATTERNS:
        match = pattern.search(head)
        if not match:
            continue
        groups = match.groupdict()
        try:
            year = int(groups["y"])
            day = int(groups["d"])
            if groups.get("mon"):
                month = _MONTH_NAMES.get(groups["mon"].lower())
                if month is None:
                    continue
            else:
                month = int(groups["m"])
            return _dt.datetime(year, month, day)
        except (ValueError, KeyError):
            continue
    return None


def combine_uploaded_texts(uploaded_files) -> str:
    """Order uploaded email threads by their best-effort detected date
    (oldest first) before concatenating, so later corrections/updates end
    up later in the combined text. Files where no date could be detected
    are appended at the end, in their original upload order.
    """
    parts = []
    for index, uploaded_file in enumerate(uploaded_files):
        text = extract_text_from_upload(uploaded_file)
        detected = _extract_likely_datetime(text)
        parts.append((detected, index, uploaded_file.name, text))

    parts.sort(key=lambda item: (item[0] is None, item[0] or _dt.datetime.min, item[1]))

    return "\n\n".join(f"----- {name} -----\n{text}" for _, _, name, text in parts)


def itinerary_to_df(stops: list[ItineraryStop]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "時間": s.time_label,
                "立ち寄り先": s.stopover_name,
                "支払額": s.payment_label,
                "支払方法": s.payment_method,
                "立ち寄り先情報": s.stopover_info,
            }
            for s in stops
        ],
        columns=ITINERARY_COLUMNS,
    )


def df_to_itinerary(df: pd.DataFrame) -> list[ItineraryStop]:
    stops = []
    for row in df.fillna("").to_dict("records"):
        if not any(str(value).strip() for value in row.values()):
            continue
        stops.append(
            ItineraryStop(
                time_label=str(row.get("時間", "")),
                stopover_name=str(row.get("立ち寄り先", "")),
                payment_label=str(row.get("支払額", "")),
                payment_method=str(row.get("支払方法", "")),
                stopover_info=str(row.get("立ち寄り先情報", "")),
            )
        )
    return stops


def _is_checked(items: list[ChecklistItem], label: str) -> bool:
    return any(item.label == label and item.done for item in items)


_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def _sanitize_filename_part(text: str) -> str:
    return _INVALID_FILENAME_CHARS.sub("-", text).strip()


def _short_date(iso_date: str) -> str:
    """e.g. '2026-06-25' -> 'Jun25', matching the "実施日（Jun09など）" convention."""
    try:
        parsed = date.fromisoformat(iso_date)
    except ValueError:
        return iso_date
    return parsed.strftime("%b%d")


def confirmation_filename(booking_no: str, tour_date: str, tour_name: str, ext: str) -> str:
    label = f"#{booking_no}" if booking_no else "#TBA"
    parts = [label, _short_date(tour_date), tour_name]
    return _sanitize_filename_part(" ".join(p for p in parts if p)) + f".{ext}"


def internal_sheet_filename(booking_no: str, tour_date: str, tour_name: str, ext: str) -> str:
    label = f"#{booking_no}" if booking_no else "#TBA"
    parts = [label, _short_date(tour_date), tour_name, "社内共有シート"]
    return _sanitize_filename_part(" ".join(p for p in parts if p)) + f".{ext}"


def guide_request_filename(guide_name: str, tour_date: str, tour_name: str, ext: str) -> str:
    guide_label = f"{guide_name}様" if guide_name and guide_name != "TBA" else "ガイドTBA様"
    parts = [guide_label, _short_date(tour_date), tour_name]
    return _sanitize_filename_part(" ".join(p for p in parts if p)) + f".{ext}"


def render_booking_form(conn, booking: BookingRequest, *, key_prefix: str) -> BookingRequest:
    """Renders the full edit form and returns the currently-edited booking.

    Call this again (it re-reads widget state) right before generating
    documents. `key_prefix` keeps widget/session_state keys distinct
    between pages (新規登録 vs ツアー詳細) that may render this same form
    for a different booking within one browser session.
    """
    st.subheader("AI抽出結果（メールから読み取った内容）")
    ac1, ac2 = st.columns(2)
    with ac1:
        tour_name = st.text_input("ツアー名", value=booking.tour_name, key=f"{key_prefix}_tour_name")
        tour_date = st.text_input("日程（YYYY-MM-DD）", value=booking.tour_date, key=f"{key_prefix}_tour_date")
        pax = st.number_input("人数", min_value=1, value=booking.pax, key=f"{key_prefix}_pax")
        time_col1, time_col2 = st.columns(2)
        with time_col1:
            start_time = st.text_input("開始時間（HH:MM）", value=booking.start_time, key=f"{key_prefix}_start_time")
        with time_col2:
            end_time = st.text_input("終了時間（HH:MM）", value=booking.end_time, key=f"{key_prefix}_end_time")
        agent = st.text_input("依頼元", value=booking.agent, key=f"{key_prefix}_agent")
        ref_no = st.text_input("依頼元Ref#（参照番号）", value=booking.ref_no, key=f"{key_prefix}_ref_no")
        agent_contact = st.text_input("依頼元担当者・連絡先", value=booking.agent_contact, key=f"{key_prefix}_agent_contact")
        inquiry_date = st.text_input("問合せ日（YYYY-MM-DD）", value=booking.inquiry_date, key=f"{key_prefix}_inquiry_date")
    with ac2:
        dietary = st.text_area("食事制限・アレルギー（英語）", value=booking.dietary, height=90, key=f"{key_prefix}_dietary")
        medical = st.text_area("メディカル", value=booking.medical, height=68, key=f"{key_prefix}_medical")
        notes = st.text_area("備考・ゲスト情報・引継ぎ", value=booking.notes, height=140, key=f"{key_prefix}_notes")

    st.subheader("社内管理・手配情報")
    guides = db.list_guides(conn)
    guide_names = ["(TBA)"] + [g.name for g in guides]

    # Auto-fill meeting point / inclusions / exclusions from the Tour
    # master when the tour name changes (still freely editable below).
    tour_master_last_key = f"{key_prefix}_tourmaster_tour_name_last"
    if tour_master_last_key not in st.session_state:
        st.session_state[tour_master_last_key] = booking.tour_name
    if st.session_state[tour_master_last_key] != tour_name:
        st.session_state[tour_master_last_key] = tour_name
        matched_tour = next((t for t in db.list_tours(conn) if t.name == tour_name), None)
        if matched_tour:
            st.session_state[f"{key_prefix}_mp_en"] = matched_tour.meeting_point_en or booking.meeting_point_en
            st.session_state[f"{key_prefix}_mp_jp"] = matched_tour.meeting_point_jp or booking.meeting_point_jp
            st.session_state[f"{key_prefix}_inclusions"] = "\n".join(matched_tour.inclusions) or "\n".join(booking.inclusions)
            st.session_state[f"{key_prefix}_exclusions"] = "\n".join(matched_tour.exclusions) or "\n".join(booking.exclusions)
            st.info(f"「{tour_name}」のタリフ情報（集合場所・Inclusions/Exclusions）を自動反映しました。")

    col1, col2 = st.columns(2)
    with col1:
        booking_no = st.text_input("予約番号（社内管理用）", value=booking.booking_no or ref_no, key=f"{key_prefix}_booking_no")
        status = st.text_input("予約状況", value=booking.status or "予約受付", key=f"{key_prefix}_status")
        payment_status = st.text_input("入金状況", value=booking.payment_status or "入金待ち", key=f"{key_prefix}_payment_status")
        assignee_1st = st.text_input("担当者(1st)", value=booking.assignee_1st, key=f"{key_prefix}_assignee_1st")
        guide_last_key = f"{key_prefix}_guide_choice_last"
        if guide_last_key not in st.session_state:
            # Seed with the booking's own guide so this doesn't look like a
            # "change" (and clobber saved mobile) on first render.
            st.session_state[guide_last_key] = booking.guide_name if booking.guide_name in guide_names else "(TBA)"

        guide_choice = st.selectbox(
            "ガイド",
            guide_names,
            index=guide_names.index(booking.guide_name) if booking.guide_name in guide_names else 0,
            key=f"{key_prefix}_guide_choice",
        )

        if st.session_state[guide_last_key] != guide_choice:
            # User just picked a different guide -- pull their mobile from
            # the guide master instead of leaving the previous guide's
            # values sitting in the form.
            st.session_state[guide_last_key] = guide_choice
            selected_guide = next((g for g in guides if g.name == guide_choice), None)
            st.session_state[f"{key_prefix}_guide_mobile"] = (selected_guide.mobile if selected_guide else "") or tbd(None)
            st.session_state[f"{key_prefix}_guide_fee_manual_base"] = (selected_guide.default_fee if selected_guide else None) or 0

        guide_mobile = st.text_input("ガイド携帯", value=booking.guide_mobile, key=f"{key_prefix}_guide_mobile")

        st.caption("ガイド謝金")
        guide_fee_auto_calc = st.checkbox(
            "宮城県発着ツアー（謝金を自動計算する。青森・山形など現地チーム手配のツアーはオフにして手入力）",
            value=booking.guide_fee_auto_calc,
            key=f"{key_prefix}_guide_fee_auto_calc",
        )

        shop_arrangement_bonus = False
        if guide_fee_auto_calc:
            if rules.is_bar_hopping_tour(tour_name):
                shop_arrangement_bonus = st.checkbox(
                    "店舗予約をガイドが担当する（+1,000円）",
                    value=booking.guide_fee_shop_arrangement_bonus,
                    key=f"{key_prefix}_shop_arrangement_bonus",
                )
            base_fee, base_formula = rules.compute_guide_base_fee(
                tour_name, pax, start_time, end_time, shop_arrangement_bonus=shop_arrangement_bonus,
            )
            if base_fee is not None:
                st.caption(f"基本謝金: {base_formula}")
            else:
                st.warning(base_formula)
                base_fee = 0
        else:
            manual_base_default = max((booking.guide_fee or 0) - booking.guide_fee_adjustment, 0)
            base_fee = st.number_input(
                "ガイド謝金（基本、手入力）", min_value=0,
                value=manual_base_default,
                step=1000, key=f"{key_prefix}_guide_fee_manual_base",
            )

        guide_fee_adjustment = st.number_input(
            "ガイド謝金（調整用。ホテル送迎などで時間が増える場合など）",
            value=booking.guide_fee_adjustment, step=500, key=f"{key_prefix}_guide_fee_adjustment",
        )

        guide_fee = int(base_fee) + int(guide_fee_adjustment)
        st.metric("ガイド謝金合計", f"¥{guide_fee:,}")

        emergency_contact = st.text_input("緊急連絡先", value=booking.emergency_contact, key=f"{key_prefix}_emergency_contact")
    with col2:
        meeting_points = db.list_meeting_points(conn)
        mp_choice_names = ["(カスタム入力)"] + [mp.name for mp in meeting_points]
        mp_last_key = f"{key_prefix}_meeting_point_last"
        if mp_last_key not in st.session_state:
            st.session_state[mp_last_key] = (
                booking.meeting_point_name if booking.meeting_point_name in mp_choice_names else "(カスタム入力)"
            )

        meeting_point_choice = st.selectbox(
            "集合場所（プルダウン。選ぶと写真もコンファメーションに反映されます）",
            mp_choice_names,
            index=mp_choice_names.index(booking.meeting_point_name) if booking.meeting_point_name in mp_choice_names else 0,
            key=f"{key_prefix}_meeting_point_choice",
        )

        if st.session_state[mp_last_key] != meeting_point_choice:
            st.session_state[mp_last_key] = meeting_point_choice
            if meeting_point_choice != "(カスタム入力)":
                selected_mp = next(mp for mp in meeting_points if mp.name == meeting_point_choice)
                st.session_state[f"{key_prefix}_mp_en"] = selected_mp.en_text
                st.session_state[f"{key_prefix}_mp_jp"] = selected_mp.jp_text

        meeting_point_en = st.text_area("集合場所（英語）", value=booking.meeting_point_en, height=100, key=f"{key_prefix}_mp_en")
        meeting_point_jp = st.text_area("集合場所（日本語）", value=booking.meeting_point_jp, height=100, key=f"{key_prefix}_mp_jp")

        if meeting_point_choice != "(カスタム入力)":
            selected_mp_preview = next(mp for mp in meeting_points if mp.name == meeting_point_choice)
            if selected_mp_preview.photo_path and Path(selected_mp_preview.photo_path).exists():
                st.image(selected_mp_preview.photo_path, width=200, caption="コンファメーションに反映される写真")
            else:
                st.caption("この集合場所には写真が未登録です（マスタ管理ページで追加できます）。")

        inclusions_text = st.text_area(
            "Inclusions（1行1項目）", value="\n".join(booking.inclusions), height=100, key=f"{key_prefix}_inclusions"
        )
        exclusions_text = st.text_area(
            "Exclusions（1行1項目）", value="\n".join(booking.exclusions), height=68, key=f"{key_prefix}_exclusions"
        )
        insurance_amount = st.number_input(
            "保険料", min_value=0, value=booking.insurance_amount or 0, step=100, key=f"{key_prefix}_insurance"
        )

    st.subheader("行程表（ガイド依頼書に反映されます）")
    tour_name_state_key = f"{key_prefix}_itinerary_tour_name"
    df_state_key = f"{key_prefix}_itinerary_df"
    variants_state_key = f"{key_prefix}_itinerary_variants"
    variant_id_state_key = f"{key_prefix}_itinerary_variant_id"

    if st.session_state.get(tour_name_state_key) != tour_name:
        st.session_state[tour_name_state_key] = tour_name
        variants = db.list_tour_itinerary_variants(conn, tour_name)
        st.session_state[variants_state_key] = variants
        if booking.tour_name == tour_name and booking.itinerary:
            st.session_state[df_state_key] = itinerary_to_df(booking.itinerary)
            st.session_state[variant_id_state_key] = None
        elif variants:
            st.session_state[df_state_key] = itinerary_to_df(variants[0].itinerary)
            st.session_state[variant_id_state_key] = variants[0].id
            st.info(
                f"「{tour_name}」の行程パターンが{len(variants)}件見つかりました。"
                f"最新の「{variants[0].label}」を読み込みました（下のプルダウンで他のパターンにも切り替えられます）。"
            )
        else:
            st.session_state[df_state_key] = itinerary_to_df([])
            st.session_state[variant_id_state_key] = None
            st.info("このツアー名の行程パターンはまだありません。下の表に入力して保存すると、次回このツアー名で呼び出せます。")

    variants: list = st.session_state[variants_state_key]
    if variants:
        picker_options = ["(現在の内容のまま)"] + [f"{v.label}｜{v.created_at[:10]}" for v in variants]
        picked = st.selectbox("保存済みの行程パターンを読み込む", picker_options, key=f"{key_prefix}_variant_picker")
        if picked != "(現在の内容のまま)":
            picked_variant = variants[picker_options.index(picked) - 1]
            loaded_key = f"{key_prefix}_variant_loaded"
            if st.session_state.get(loaded_key) != picked_variant.id:
                st.session_state[loaded_key] = picked_variant.id
                st.session_state[df_state_key] = itinerary_to_df(picked_variant.itinerary)
                st.session_state[variant_id_state_key] = picked_variant.id

    itinerary_df = st.data_editor(
        st.session_state[df_state_key],
        num_rows="dynamic",
        width="stretch",
        key=f"{key_prefix}_itinerary_editor",
    )

    current_variant_id = st.session_state.get(variant_id_state_key)
    current_label = next((v.label for v in variants if v.id == current_variant_id), "")
    save_label = st.text_input(
        "行程パターン名（保存時のラベル）",
        value=current_label or date.today().isoformat(),
        key=f"{key_prefix}_itinerary_label",
    )

    save_col1, save_col2 = st.columns(2)
    with save_col1:
        if st.button("新しい行程パターンとして保存（コピー）", key=f"{key_prefix}_save_new_variant"):
            stops_to_save = df_to_itinerary(itinerary_df)
            db.save_tour_itinerary_variant(conn, tour_name, save_label or date.today().isoformat(), stops_to_save)
            st.session_state[variants_state_key] = db.list_tour_itinerary_variants(conn, tour_name)
            st.success(f"「{save_label}」として新しく保存しました（既存のパターンは変更していません）。")
    with save_col2:
        if current_variant_id and st.button("選択中のパターンを上書き保存", key=f"{key_prefix}_overwrite_variant"):
            stops_to_save = df_to_itinerary(itinerary_df)
            db.update_tour_itinerary_variant(conn, current_variant_id, save_label or current_label, stops_to_save)
            st.session_state[variants_state_key] = db.list_tour_itinerary_variants(conn, tour_name)
            st.success(f"「{save_label}」を上書き保存しました。")

    st.subheader("手配状況チェックリスト")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("予約前対応")
        pre_done = {
            label: st.checkbox(label, value=_is_checked(booking.checklist_pre, label), key=f"{key_prefix}_pre_{label}")
            for label in CHECKLIST_LABELS["pre"]
        }
    with c2:
        st.caption("ツアー関連対応")
        during_done = {
            label: st.checkbox(label, value=_is_checked(booking.checklist_during, label), key=f"{key_prefix}_during_{label}")
            for label in CHECKLIST_LABELS["during"]
        }
    with c3:
        st.caption("ツアー後")
        post_done = {
            label: st.checkbox(label, value=_is_checked(booking.checklist_post, label), key=f"{key_prefix}_post_{label}")
            for label in CHECKLIST_LABELS["post"]
        }

    return replace(
        booking,
        tour_name=tour_name,
        tour_date=tour_date,
        pax=pax,
        start_time=start_time,
        end_time=end_time,
        agent=agent,
        ref_no=ref_no,
        agent_contact=agent_contact,
        inquiry_date=inquiry_date,
        dietary=dietary,
        medical=medical,
        notes=notes,
        booking_no=booking_no,
        status=status,
        payment_status=payment_status,
        assignee_1st=assignee_1st,
        guide_name=guide_choice if guide_choice != "(TBA)" else "TBA",
        guide_mobile=guide_mobile,
        guide_fee=guide_fee or None,
        guide_fee_auto_calc=guide_fee_auto_calc,
        guide_fee_shop_arrangement_bonus=shop_arrangement_bonus,
        guide_fee_adjustment=int(guide_fee_adjustment),
        emergency_contact=emergency_contact,
        meeting_point_name=meeting_point_choice if meeting_point_choice != "(カスタム入力)" else "",
        meeting_point_en=meeting_point_en,
        meeting_point_jp=meeting_point_jp,
        inclusions=[line for line in inclusions_text.splitlines() if line.strip()],
        exclusions=[line for line in exclusions_text.splitlines() if line.strip()],
        insurance_amount=insurance_amount or None,
        itinerary=df_to_itinerary(itinerary_df),
        checklist_pre=[ChecklistItem(label, done) for label, done in pre_done.items()],
        checklist_during=[ChecklistItem(label, done) for label, done in during_done.items()],
        checklist_post=[ChecklistItem(label, done) for label, done in post_done.items()],
    )


def generate_documents(conn, updated: BookingRequest) -> None:
    """Generate the 3 documents + PDFs for this session only, and stash the
    results in st.session_state so render_downloads() can show them
    persistently (including across reruns triggered by download clicks).

    Deliberately stateless: nothing here is written to a database. This
    tool only generates and hands off files -- the source email/PDF stays
    in Google Drive as before, and this app never accumulates a history of
    past bookings. Only reference master data (guides/agents/tours/
    stopovers/meeting points/itinerary variants) persists, via db.py.
    """
    out_dir = GENERATED_DIR / (updated.booking_no or "current")
    out_dir.mkdir(parents=True, exist_ok=True)

    meeting_point_photo_path = None
    if updated.meeting_point_name:
        matched_mp = next(
            (mp for mp in db.list_meeting_points(conn) if mp.name == updated.meeting_point_name), None
        )
        if matched_mp and matched_mp.photo_path:
            meeting_point_photo_path = matched_mp.photo_path

    with st.spinner("Excel/PowerPointを生成中..."):
        workbook_path = generate_tour_workbook(
            updated, out_dir / "tour_workbook.xlsx", meeting_point_photo_path=meeting_point_photo_path
        )
        pptx_path = generate_guide_request(updated, out_dir / "guide_request.pptx")
    st.success("Excel/PowerPointを生成しました。")

    internal_pdf = confirmation_pdf = guide_pdf = None
    try:
        with st.spinner("PDFを書き出し中（LibreOffice）..."):
            internal_pdf = export_workbook_sheet_pdf(workbook_path, "予約情報", out_dir / "internal_sheet.pdf")
            confirmation_pdf = export_workbook_sheet_pdf(
                workbook_path, "予約確認書(Oyster)", out_dir / "booking_confirmation.pdf"
            )
            guide_pdf = convert_to_pdf(pptx_path, out_dir)
        st.success("PDFを書き出しました。")
    except PdfExportError as exc:
        st.error(f"PDF書き出しに失敗しました: {exc}")

    st.session_state["last_generated"] = {
        "booking_no": updated.booking_no,
        "tour_date": updated.tour_date,
        "tour_name": updated.tour_name,
        "guide_name": updated.guide_name,
        "workbook_path": str(workbook_path),
        "pptx_path": str(pptx_path),
        "internal_pdf": str(internal_pdf) if internal_pdf else None,
        "confirmation_pdf": str(confirmation_pdf) if confirmation_pdf else None,
        "guide_pdf": str(guide_pdf) if guide_pdf else None,
    }


def _booking_out_dir(generated: dict) -> Path:
    out_dir = GENERATED_DIR / (generated["booking_no"] or "current")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def save_meeting_point_photo(image_bytes: bytes, meeting_point_id: int) -> str:
    """Normalize any uploaded/extracted image to PNG and store it under
    data/ (gitignored), keyed by meeting point id so re-saving just
    overwrites the same file. Returns the saved path as a string.
    """
    from io import BytesIO

    from PIL import Image

    MEETING_POINT_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    photo_path = MEETING_POINT_PHOTOS_DIR / f"{meeting_point_id}.png"
    image = Image.open(BytesIO(image_bytes))
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    image.save(photo_path, format="PNG")
    return str(photo_path)


def render_downloads() -> None:
    generated = st.session_state.get("last_generated")
    if not generated:
        return

    booking_no = generated["booking_no"]
    tour_date = generated["tour_date"]
    tour_name = generated["tour_name"]
    guide_name = generated["guide_name"]

    st.header(f"ダウンロード（予約番号: {booking_no or '(未設定)'}）")
    dl1, dl2 = st.columns(2)
    with dl1:
        st.write("**社内共有シート＋Booking Confirmation（編集用原本）**")
        if generated["workbook_path"] and Path(generated["workbook_path"]).exists():
            p = Path(generated["workbook_path"])
            name = confirmation_filename(booking_no, tour_date, tour_name, "xlsx")
            st.download_button("Excelをダウンロード", p.read_bytes(), file_name=name, key="dl_workbook")
        if generated["internal_pdf"] and Path(generated["internal_pdf"]).exists():
            p = Path(generated["internal_pdf"])
            name = internal_sheet_filename(booking_no, tour_date, tour_name, "pdf")
            st.download_button("社内共有シートPDF", p.read_bytes(), file_name=name, key="dl_internal_pdf")
        if generated["confirmation_pdf"] and Path(generated["confirmation_pdf"]).exists():
            p = Path(generated["confirmation_pdf"])
            name = confirmation_filename(booking_no, tour_date, tour_name, "pdf")
            st.download_button("Booking Confirmation PDF", p.read_bytes(), file_name=name, key="dl_confirmation_pdf")

        st.caption("Excelをデスクトップで手直しした場合は、ここに再アップロードするとそのファイルからPDFを作り直せます。")
        uploaded_xlsx = st.file_uploader("修正済みExcelを再アップロード", type=["xlsx"], key="reupload_xlsx")
        if uploaded_xlsx is not None:
            out_dir = _booking_out_dir(generated)
            edited_path = out_dir / "tour_workbook_edited.xlsx"
            edited_path.write_bytes(uploaded_xlsx.getvalue())
            try:
                edited_internal_pdf = export_workbook_sheet_pdf(
                    edited_path, "予約情報", out_dir / "internal_sheet_edited.pdf"
                )
                edited_confirmation_pdf = export_workbook_sheet_pdf(
                    edited_path, "予約確認書(Oyster)", out_dir / "booking_confirmation_edited.pdf"
                )
                st.success("修正済みExcelからPDFを作り直しました。")
                st.download_button(
                    "社内共有シートPDF（修正版）", edited_internal_pdf.read_bytes(),
                    file_name=internal_sheet_filename(booking_no, tour_date, tour_name, "pdf"),
                    key="dl_internal_pdf_edited",
                )
                st.download_button(
                    "Booking Confirmation PDF（修正版）", edited_confirmation_pdf.read_bytes(),
                    file_name=confirmation_filename(booking_no, tour_date, tour_name, "pdf"),
                    key="dl_confirmation_pdf_edited",
                )
            except PdfExportError as exc:
                st.error(f"PDF変換に失敗しました: {exc}")
    with dl2:
        st.write("**ガイド依頼書（編集用原本）**")
        if generated["pptx_path"] and Path(generated["pptx_path"]).exists():
            p = Path(generated["pptx_path"])
            name = guide_request_filename(guide_name, tour_date, tour_name, "pptx")
            st.download_button("PowerPointをダウンロード", p.read_bytes(), file_name=name, key="dl_pptx")
        if generated["guide_pdf"] and Path(generated["guide_pdf"]).exists():
            p = Path(generated["guide_pdf"])
            name = guide_request_filename(guide_name, tour_date, tour_name, "pdf")
            st.download_button("ガイド依頼書PDF", p.read_bytes(), file_name=name, key="dl_guide_pdf")

        st.caption("PowerPointをデスクトップで手直しした場合は、ここに再アップロードするとそのファイルからPDFを作り直せます。")
        uploaded_pptx = st.file_uploader("修正済みPowerPointを再アップロード", type=["pptx"], key="reupload_pptx")
        if uploaded_pptx is not None:
            out_dir = _booking_out_dir(generated)
            edited_pptx_path = out_dir / "guide_request_edited.pptx"
            edited_pptx_path.write_bytes(uploaded_pptx.getvalue())
            try:
                edited_guide_pdf = convert_to_pdf(edited_pptx_path, out_dir)
                st.success("修正済みPowerPointからPDFを作り直しました。")
                st.download_button(
                    "ガイド依頼書PDF（修正版）", edited_guide_pdf.read_bytes(),
                    file_name=guide_request_filename(guide_name, tour_date, tour_name, "pdf"),
                    key="dl_guide_pdf_edited",
                )
            except PdfExportError as exc:
                st.error(f"PDF変換に失敗しました: {exc}")
