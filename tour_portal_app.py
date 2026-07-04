"""ツアー予約割当ポータル - エントリーポイント（ローカル専用）。

実際の画面は pages/ 以下にあります:
  1_新規登録.py    メール(PDF)取り込み・AI抽出・書類生成（その場限り、DBに保存しない）
  2_マスタ管理.py   ガイド・依頼元・ツアー・立ち寄り先単価の管理

個々の予約データ（メール本文・ゲスト情報等）はこのアプリに蓄積しない。保持する
のはタリフ・ガイド等のマスタ情報のみ。予約ごとのやり取りは従来どおりGoogle
ドライブにPDFで保存する運用のまま。

Run locally with run_portal.command, or directly:
    PYTHONPATH=src streamlit run tour_portal_app.py
"""

from __future__ import annotations

import streamlit as st

from portal_common import ensure_api_key, get_conn
from tlst_automation import db

st.set_page_config(page_title="ツアー予約割当ポータル", layout="wide")
ensure_api_key()
conn = get_conn()

st.title("ツアー予約割当ポータル")
st.write("左のサイドバーから画面を選んでください。")

st.metric(
    "ガイド・依頼元・ツアー・立ち寄り先マスタ",
    f"{len(db.list_guides(conn))}/{len(db.list_agents(conn))}/{len(db.list_tours(conn))}/{len(db.list_stopovers(conn))}",
)

st.page_link("pages/1_新規登録.py", label="新規ツアー登録（書類作成）", icon="📝")
st.page_link("pages/2_マスタ管理.py", label="マスタ管理", icon="🗂️")
