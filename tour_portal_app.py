"""ツアー予約割当ポータル - エントリーポイント。

実際の画面は pages/ 以下にあります:
  1_新規登録.py    メール(PDF)取り込み・AI抽出・書類生成
  2_ツアー一覧.py   予約の検索・絞り込み
  3_ツアー詳細.py   既存予約の確認・編集・再生成
  4_マスタ管理.py   ガイド・依頼元・ツアー・立ち寄り先単価の管理

Run with:
    PYTHONPATH=src streamlit run tour_portal_app.py
"""

from __future__ import annotations

import streamlit as st

from portal_common import ensure_api_key, get_conn, require_login
from tlst_automation import db

st.set_page_config(page_title="ツアー予約割当ポータル", layout="wide")
require_login()
ensure_api_key()
conn = get_conn()

st.title("ツアー予約割当ポータル")
st.write("左のサイドバーから画面を選んでください。")

bookings = db.list_bookings(conn)
col1, col2 = st.columns(2)
col1.metric("登録済みツアー数", len(bookings))
col2.metric(
    "ガイド・依頼元・ツアー・立ち寄り先マスタ",
    f"{len(db.list_guides(conn))}/{len(db.list_agents(conn))}/{len(db.list_tours(conn))}/{len(db.list_stopovers(conn))}",
)

st.page_link("pages/1_新規登録.py", label="新規ツアー登録", icon="📝")
st.page_link("pages/2_ツアー一覧.py", label="ツアー一覧", icon="📋")
st.page_link("pages/3_ツアー詳細.py", label="ツアー詳細／編集", icon="🔍")
st.page_link("pages/4_マスタ管理.py", label="マスタ管理", icon="🗂️")
