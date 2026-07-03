"""ツアー一覧: 予約番号・ツアー名・予約状況・入金状況などで検索・絞り込みし、詳細画面を開く。"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portal_common import get_conn, require_login  # noqa: E402
from tlst_automation import db  # noqa: E402

st.set_page_config(page_title="ツアー一覧 - ツアー予約割当ポータル", layout="wide")
require_login()
conn = get_conn()

st.title("ツアー一覧")

rows = [dict(row) for row in db.list_bookings(conn)]

if not rows:
    st.caption("まだ保存された予約はありません。「新規登録」からツアーを登録してください。")
else:
    df = pd.DataFrame(rows)

    col1, col2, col3 = st.columns(3)
    with col1:
        query = st.text_input("予約番号・ツアー名で検索")
    with col2:
        status_options = ["(すべて)"] + sorted(v for v in df["status"].dropna().unique().tolist() if v)
        status_filter = st.selectbox("予約状況", status_options)
    with col3:
        payment_options = ["(すべて)"] + sorted(v for v in df["payment_status"].dropna().unique().tolist() if v)
        payment_filter = st.selectbox("入金状況", payment_options)

    filtered = df
    if query:
        mask = (
            filtered["booking_no"].fillna("").str.contains(query, case=False)
            | filtered["tour_name"].fillna("").str.contains(query, case=False)
        )
        filtered = filtered[mask]
    if status_filter != "(すべて)":
        filtered = filtered[filtered["status"] == status_filter]
    if payment_filter != "(すべて)":
        filtered = filtered[filtered["payment_status"] == payment_filter]

    st.caption(f"{len(filtered)} 件 / 全 {len(df)} 件")

    display_columns = [
        "booking_no", "tour_name", "tour_date", "pax", "status",
        "payment_status", "agent", "guide_name",
    ]
    event = st.dataframe(
        filtered[display_columns],
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tour_list_table",
    )

    selected_rows = event.selection.rows if event and event.selection else []
    if selected_rows:
        selected = filtered.iloc[selected_rows[0]]
        st.session_state["selected_booking_id"] = int(selected["id"])
        if st.button(f"予約番号「{selected['booking_no'] or selected['id']}」の詳細を開く", type="primary"):
            st.switch_page("pages/3_ツアー詳細.py")
