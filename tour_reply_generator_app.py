import streamlit as st

st.set_page_config(page_title="Tour Reply Generator", layout="wide")

st.title("🧭 TLST 返信文作成ツール")

# --- 設定エリア ---
col1, col2, col3, col4, col5, col6 = st.columns(6)
with col1:
    mode = st.selectbox("返信タイプ", ["AGT", "EXO", "BtoC"])
with col2:
    pax = st.number_input("人数", min_value=1, value=2)
# 👇 EXO のときは G/PV を表示しない
with col3:
    if mode != "EXO":
        type_ = st.selectbox("タイプ", ["G", "PV"])
    else:
        type_ = "G"  # ダミー値を設定（計算には影響しない）
with col4:
    language = st.selectbox("言語", ["JP", "EN"])

# --- ツアー一覧 ---
tours = {
    "hungry": {"name": "Hungry Samurai: Sendai Food & Culture Day Tour", "price": 30000},
    "barhop_sendai": {"name": "Back-alley Bar Hopping in Sendai", "price": 20000},
    "shiogama10": {"name": "Shiogama’s 10 Tasting Treasures", "price": 24000},
    "culinary": {"name": "Culinary Walking Tour in Sendai", "price": 15000},
    "cruise8_14": {"name": "Cruise with an Oyster Fisherman (8:00–14:00, Matsushima)", "price": 40000},
    "oyster10_15": {"name": "Oyster Cruise & Local Lunch (10:00–15:00, Matsushima)", "price": 32000},
    "delicacy": {"name": "Seafood Delicacy Tour", "price": 35000}
}

exo_tours = {
    "barhop_exo": {"name": "Sendai Bar Hopping Tour (EXO)", "price": 25960},
    "hungry_samurai_fd": {"name": "Hungry Samurai (SendaiFD, EXO)", "price": 38500},
    "hirosaki_aomori_fd": {"name": "Hirosaki & Aomori Full Day Tour (EXO)", "price": 000},
    "hirosaki_hd": {"name": "Hirosaki Half Day Tour (EXO)", "price": 000},
    "hiraizumi": {"name": "Hiraizumi Full Day Tour (EXO)", "price": 89650},
    "sendai_hd": {"name": "Sendai Half Day Tour (EXO)", "price": 38500},
    "matsushima_shiogama_fd": {"name": "Shiogama's Delicacy Trail to Matsushima's Natural Wonders (EXO)", "price": 41800},
    "private_transfer": {"name": "Oneway Private Transfer: Sendai → Matsushima (EXO)", "price": 19800, "perVehicle": True},
    "private_transfer_hiace": {"name": "Oneway Private Transfer: Sendai → Matsushima (Hiace, EXO)", "price": 26400, "perVehicle": True}
}

tour_list = exo_tours if mode == "EXO" else tours

with col5:
    tour = st.selectbox("ツアーを選択", list(tour_list.keys()), format_func=lambda x: tour_list[x]["name"])

# --- 入力欄 ---
st.subheader("📥 受信メール本文を貼り付け")
email_text = st.text_area("メール内容", height=150, placeholder="Paste the received email here...")

# --- 出力 ---
log = []
output = ""

def log_event(msg):
    log.append(msg)

def extract_name(text):
    import re
    patterns = [r"Dear\\s+([A-Z][a-zA-Z]+)", r"Hello\\s+([A-Z][a-zA-Z]+)", r"Hi\\s+([A-Z][a-zA-Z]+)", r"To:\\s*([A-Z][a-zA-Z]+)"]
    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group(1)
    return "[Customer Name]"

if st.button("✉️ 返信文を生成"):
    tour_data = tour_list[tour]
    name = extract_name(email_text)
    base = tour_data.get("price", 0)
    per_vehicle = tour_data.get("perVehicle", False)
    qty_pax = pax if not per_vehicle else 1  # 人数 or 1台

    # --- 計算 ---
    if mode == "EXO":
        # EXO: 税込・PV加算なし・人数(または車両数)で単純乗算
        subtotal = base * qty_pax
        total = subtotal
        total_str = f"{total:,}"
        # 表示用の数式（英語/日本語は後段のテンプレで使う）
        formula_en = f"({base:,} yen × {qty_pax} {'vehicle' if per_vehicle else 'pax'}) = **{total_str} yen (tax included)**"
        formula_jp = f"（{base:,}円 × {qty_pax}{'台' if per_vehicle else '名'}）＝ **{total_str}円（税込）**"
    else:
        # AGT/BtoC 通常: 税抜×人数 +（PVなら1万円）→ ×1.1
        subtotal = base * pax + (10000 if type_ == "PV" else 0)
        total = round(subtotal * 1.1)
        total_str = f"{total:,}"
        formula_en = f"({base:,} yen × {pax} pax{(' + 10,000 yen private guarantee fee' if type_ == 'PV' else '')}) × 1.1 tax = **{total_str} yen (tax included)**"
        formula_jp = f"（{base:,}円 × {pax}名{(' ＋ 10,000円（プライベート確約料）' if type_ == 'PV' else '')}）× 消費税1.1 ＝ **{total_str}円（税込）**"

    # 👇 共通で定義（これが抜けていた）
    total_str = f"{total:,}"

    # --- 以下は出力文生成 ---

    if mode == "BtoC":
            output = f"""Subject: Booking Request Received – {tour_data['name']}

Dear {name},

Thank you very much for your message.

We have received your booking request for:
★ {tour_data['name']}
({base:,} yen × {pax} pax{(' + 10,000 yen private guarantee fee' if type_ == 'PV' else '')}) × 1.1 tax = **{total_str} yen (tax included)**

We will coordinate with our guides and get back to you once arrangements have been made on XXXX-XX-XX (date).

Please note that once a guide is secured, the booking will require advance payment.
We will send you a payment link through Square (our payment processing platform), and the reservation will be confirmed upon receipt of payment.

Please wait for our next update.

Best regards,
Kyoko 
Tohoku Local Secret Tours
"""

    else:
        if language == "JP":
            output = f"""件名：【ご予約確認】{tour_data['name']}

いつもお世話になっております。
以下の内容でお受けいたします。
★ {tour_data['name']}
{formula_jp}

ツアー実施の約1か月前に、ガイド名を含む最終確認書（PDF）をお送りいたします。
本メール中にツアー終了後の請求予定金額として上記をご案内いたします。

何卒よろしくお願いいたします。
小野寺"""

        else:
            output = f"""Subject: Booking Confirmation – {tour_data['name']}

Dear {name},

Thank you very much for your continued support and for your new booking request.
We are pleased to confirm the reservation as follows:

★ {tour_data['name']}
{formula_en}

We will send a PDF confirmation approximately one month before the tour, including the guide’s name and final details.
To ensure accuracy, we have also reconfirm in this email the total amount to be invoiced after the tour.

Thank you very much for your cooperation.
Kind regards,
Kyoko"""

# --- 出力表示 ---
if output:
    st.subheader("📤 生成された返信文")
    st.code(output, language="markdown")

