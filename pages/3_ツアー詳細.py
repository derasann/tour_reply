"""ツアー詳細／編集: 既存予約の内容確認・修正、書類の再生成・再ダウンロード。"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portal_common import (  # noqa: E402
    generate_and_persist,
    get_conn,
    load_last_generated_from_db,
    render_booking_form,
    render_downloads,
    require_login,
)
from tlst_automation import db  # noqa: E402

st.set_page_config(page_title="ツアー詳細 - ツアー予約割当ポータル", layout="wide")
require_login()
conn = get_conn()

st.title("ツアー詳細／編集")

bookings = db.list_bookings(conn)
if not bookings:
    st.caption("まだ保存された予約はありません。「新規登録」からツアーを登録してください。")
    st.stop()

id_to_label = {
    row["id"]: f"{row['booking_no'] or '(番号未設定)'} - {row['tour_name']} ({row['tour_date']})"
    for row in bookings
}

default_id = st.session_state.get("selected_booking_id")
options = list(id_to_label.keys())
default_index = options.index(default_id) if default_id in options else 0

selected_id = st.selectbox(
    "予約を選択",
    options,
    index=default_index,
    format_func=lambda booking_id: id_to_label[booking_id],
)
st.session_state["selected_booking_id"] = selected_id

booking = db.get_booking(conn, selected_id)
if booking is None:
    st.error("この予約は見つかりませんでした。")
    st.stop()

load_last_generated_from_db(conn, selected_id, booking)

updated = render_booking_form(conn, booking, key_prefix="detail")

save_col, generate_col = st.columns(2)
with save_col:
    if st.button("変更を保存（書類は再生成しない）", key="detail_save"):
        db.update_booking(conn, selected_id, updated)
        st.success("保存しました。")
with generate_col:
    if st.button("変更を保存して書類を再生成する", type="primary", key="detail_generate"):
        generate_and_persist(conn, updated, booking_id=selected_id)

st.divider()
render_downloads()
