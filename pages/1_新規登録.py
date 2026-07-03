"""新規ツアー登録: メール(PDF)のドラッグ＆ドロップ or 貼り付け -> AI抽出 -> 確認・補完 -> 書類生成。"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portal_common import (  # noqa: E402
    ensure_api_key,
    extract_text_from_upload,
    generate_and_persist,
    get_conn,
    render_booking_form,
    render_downloads,
    require_login,
)
from tlst_automation.ai_extractor import ExtractionError, extract_booking_request  # noqa: E402

st.set_page_config(page_title="新規登録 - ツアー予約割当ポータル", layout="wide")
require_login()
ensure_api_key()
conn = get_conn()

st.title("新規ツアー登録")

if "booking" not in st.session_state:
    st.session_state.booking = None

st.header("1. メールのやり取りをドラッグ＆ドロップ")
uploaded_files = st.file_uploader(
    "保存済みのメール本文（PDF）をここにドラッグ＆ドロップしてください。複数通まとめて選択できます。",
    type=["pdf", "txt"],
    accept_multiple_files=True,
)
st.caption(
    "複数のPDFをまとめて渡した場合、現時点では時系列に連結してAIに渡します"
    "（やり取りの中から最新の情報を自動で整理する機能は次の実装で対応します）。"
)

if uploaded_files:
    upload_signature = tuple((f.name, f.size) for f in uploaded_files)
    if st.session_state.get("_upload_signature") != upload_signature:
        st.session_state["_upload_signature"] = upload_signature
        parts = [
            f"----- {f.name} -----\n{extract_text_from_upload(f)}" for f in uploaded_files
        ]
        st.session_state["email_text"] = "\n\n".join(parts)

email_text = st.text_area(
    "抽出されたテキスト（内容を確認・手直しできます。直接貼り付けも可）",
    height=260,
    key="email_text",
)

if st.button("AIで抽出する", type="primary"):
    if not email_text.strip():
        st.warning("メール本文を貼り付けてください。")
    else:
        try:
            with st.spinner("Claudeで抽出中..."):
                st.session_state.booking = extract_booking_request(email_text)
            st.success("抽出しました。下のフォームで内容を確認・補完してください。")
        except ExtractionError as exc:
            st.error(f"抽出に失敗しました: {exc}")

booking = st.session_state.booking

if booking is not None:
    st.header("2. 内容の確認・補完")
    updated = render_booking_form(conn, booking, key_prefix="new")

    if st.button("書類を生成する", type="primary", key="new_generate"):
        generate_and_persist(conn, updated, booking_id=None)

st.divider()
render_downloads()
