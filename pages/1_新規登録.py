"""新規ツアー登録: メール(PDF)のドラッグ＆ドロップ or 貼り付け -> AI抽出 -> 確認・補完 -> 書類生成。"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portal_common import (  # noqa: E402
    clear_draft_booking,
    combine_uploaded_texts,
    ensure_api_key,
    generate_documents,
    get_conn,
    load_draft_booking,
    render_booking_form,
    render_downloads,
    save_draft_booking,
)
from tlst_automation.ai_extractor import ExtractionError, extract_booking_request  # noqa: E402

st.set_page_config(page_title="新規登録 - ツアー予約割当ポータル", layout="wide")
ensure_api_key()
conn = get_conn()

st.title("新規ツアー登録")

if "booking" not in st.session_state:
    st.session_state.booking = None

if st.session_state.booking is None and not st.session_state.get("_draft_dismissed"):
    draft = load_draft_booking()
    if draft is not None:
        st.info(
            f"前回保存した下書きがあります：「{draft.tour_name or '(ツアー名未入力)'}」"
            f"（{draft.tour_date or '日程未入力'}）"
        )
        draft_col1, draft_col2 = st.columns(2)
        with draft_col1:
            if st.button("この下書きを読み込む", key="load_draft"):
                st.session_state.booking = draft
                st.rerun()
        with draft_col2:
            if st.button("下書きを破棄する", key="discard_draft"):
                clear_draft_booking()
                st.session_state["_draft_dismissed"] = True
                st.rerun()

st.header("1. メールのやり取りをドラッグ＆ドロップ")
uploaded_files = st.file_uploader(
    "保存済みのメール本文（PDF）をここにドラッグ＆ドロップしてください。複数通まとめて選択できます。",
    type=["pdf", "txt"],
    accept_multiple_files=True,
)
st.caption(
    "複数のPDFをまとめて渡した場合、本文中の日付を見て時系列（古い→新しい）に並べ替えてから"
    "AIに渡します。日付が見つからないファイルは末尾に追加されます。"
    "AI自身にも「内容が矛盾する場合は日時から見て最新の情報を優先する」よう指示しています"
    "（完全な保証ではないので、抽出結果は必ず確認してください）。"
)

if uploaded_files:
    upload_signature = tuple((f.name, f.size) for f in uploaded_files)
    if st.session_state.get("_upload_signature") != upload_signature:
        st.session_state["_upload_signature"] = upload_signature
        st.session_state["email_text"] = combine_uploaded_texts(uploaded_files)

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

    save_col, generate_col = st.columns(2)
    with save_col:
        if st.button("💾 下書きを保存する", key="save_draft"):
            st.session_state.booking = updated
            save_draft_booking(updated)
            st.success("下書きを保存しました。ブラウザを閉じても、次回このページを開くと読み込めます。")
    with generate_col:
        if st.button("書類を生成する", type="primary", key="new_generate"):
            generate_documents(conn, updated)

st.divider()
render_downloads()
