import streamlit as st

st.set_page_config(page_title="Tour Reply Generator", layout="wide")

st.title("🧭 TLST 返信文作成ツール")

# --- 設定エリア ---
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    mode = st.selectbox("返信タイプ", ["AGT", "EXO", "BtoC"])

with col2:
    pax = st.number_input("人数", min_value=1, value=2)

with col3:
    if mode != "EXO":
        type_ = st.selectbox("タイプ", ["G", "PV"])
    else:
        type_ = "G"

with col4:
    language = st.selectbox("言語", ["JP", "EN"])

# --- ツアー一覧（AGT / BtoC 共通）税抜単価 ---
tours = {
    # 仙台・宮城
    "hungry": {
        "name": "Hungry Samurai: Sendai Food & Culture Day Tour (with cab)",
        "price": 30000
    },
    "barhop_sendai": {
        "name": "Back-alley Night Izakaya Hopping in Sendai",
        "price": 20000
    },
    "barhop_sendai_veg": {
        "name": "Bar Hopping in Kokubuncho VEG (Sendai)",
        "price": 20000
    },
    "culinary": {
        "name": "Foodie Delight: Culinary Walking Tour (150 min)",
        "price": 15000
    },
    "shiogama10": {
        "name": "Shiogama's 10 Tasting Treasures",
        "price": 24000
    },
    "delicacy": {
        "name": "Shiogama's Delicacy Trail to Matsushima's Natural Wonders",
        "price": 35000
    },
    "oyster_jrtrain": {
        "name": "Oyster Fisherman's Cruise & Seasonal Feast (JR train)",
        "price": 32000
    },
    "oyster_matsushima": {
        "name": "Cruise with Oyster Fisherman + All-you-can-eat Oyster, Matsushima (JR & cab)",
        "price": 40000
    },
    "fish_feast": {
        "name": "Fish & Feast with Local Fisherman! Fishing, Local Traditions, and BBQ Lunch",
        "price": 32000
    },
    # 東北各地バーホッピング
    "barhop_hachinohe": {
        "name": "Nightlife & Tradition: Hachinohe Yokocho Izakaya Experience (Aomori)",
        "price": 20000
    },
    "barhop_miyako": {
        "name": "Back-alley Bar Hopping in Miyako (Iwate)",
        "price": 20000
    },
    "barhop_tsuruoka": {
        "name": "Bar Hopping in Tsuruoka (Yamagata)",
        "price": 20000
    },
    "barhop_dake": {
        "name": "Dake Onsen Bar Hopping Tour (Fukushima)",
        "price": 20000
    },
    "barhop_kakunodate": {
        "name": "Izakaya and Japanese 'Snack Bar' Tour in Kakunodate (Akita)",
        "price": 20000
    },
    # Attracxi系（2名基準 税抜90,000円/人）
    "attracxi_dewa": {
        "name": "Attracxi: Mysteries of the Three Holy Mountains of Dewa",
        "price": 90000
    },
    "attracxi_hiraizumi": {
        "name": "Attracxi: Hiraizumi Full Day Tour from Sendai",
        "price": 90000
    },
    "attracxi_samurai": {
        "name": "Attracxi: Master the Way of the Samurai",
        "price": 90000
    },
    "attracxi_shiogama_matsushima": {
        "name": "Attracxi: Shiogama's Delicacy Trail to Matsushima's Natural Wonders",
        "price": 90000
    },
    "attracxi_cask": {
        "name": "Attracxi: From Cask to Glass – Tohoku's Craft Journey with Local Cuisine",
        "price": 90000
    },
    "attracxi_naruko": {
        "name": "Attracxi: Step into Tradition – Craft, Culture, and Hot Springs in Naruko",
        "price": 90000
    },
}

# --- EXO専用ツアーリスト（税込単価）---
exo_tours = {
    "barhop_exo": {
        "name": "Sendai Bar Hopping Tour (EXO)",
        "price": 25960
    },
    "hungry_samurai_fd": {
        "name": "Hungry Samurai: Sendai Food & Culture Day Tour (EXO)",
        "price": 38500
    },
    "matsushima_shiogama_fd": {
        "name": "Matsushima & Shiogama Full Day Tour (EXO)",
        "price": 41800
    },
    "hiraizumi": {
        "name": "Hiraizumi Full Day Tour from Sendai (EXO)",
        "price": 89650
    },
    "hirosaki_hd": {
        "name": "HD Tour of Hirosaki (EXO)",
        "price": 25000
    },
    "hirosaki_aomori_fd": {
        "name": "Hirosaki & Aomori Full Day Tour (EXO)",
        "price": 35000
    },
    "dewa_sanzan_sendai": {
        "name": "The Sacred Peaks of Yamagata Day Trip from Sendai (EXO)",
        "price": 0  # 要確認：EXOタリフに記載なし
    },
    "private_transfer": {
        "name": "Oneway Private Transfer: Sendai → Matsushima (EXO)",
        "price": 19800,
        "perVehicle": True
    },
    "private_transfer_hiace": {
        "name": "Oneway Private Transfer: Sendai → Matsushima (Hiace, EXO)",
        "price": 26400,
        "perVehicle": True
    },
    "guide_assistant_on_foot": {
        "name": "Guide Assistant On foot (Shin-Aomori / Sendai Station, EXO)",
        "price": 19800,
        "perGroup": True
    },
    "guide_assistant_private_car": {
        "name": "Guide Assistant Private Car (Shin-Aomori / Sendai Station, EXO)",
        "price": 30800,
        "perGroup": True
    },
}

tour_list = exo_tours if mode == "EXO" else tours

with col5:
    tour = st.selectbox(
        "ツアーを選択",
        list(tour_list.keys()),
        format_func=lambda x: tour_list[x]["name"]
    )

# --- 入力欄 ---
st.subheader("📥 受信メール本文を貼り付け")
email_text = st.text_area("メール内容", height=150, placeholder="Paste the received email here...")

# --- ユーティリティ ---
def extract_name(text):
    import re
    patterns = [
        r"Dear\s+([A-Z][a-zA-Z\-]+)",
        r"Hello\s+([A-Z][a-zA-Z\-]+)",
        r"Hi\s+([A-Z][a-zA-Z\-]+)",
        r"To:\s*([A-Z][a-zA-Z\-]+)"
    ]
    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group(1)
    return "[Customer Name]"

# --- 生成ボタン ---
if st.button("✉️ 返信文を生成"):
    tour_data = tour_list[tour]
    name = extract_name(email_text)
    base = tour_data.get("price", 0)
    per_vehicle = tour_data.get("perVehicle", False)
    per_group = tour_data.get("perGroup", False)
    qty = 1 if (per_vehicle or per_group) else pax

    # --- 料金計算 ---
    if mode == "EXO":
        total = base * qty
        total_str = f"{total:,}"
        if per_vehicle:
            unit_label = "vehicle"
            unit_jp = "台"
        elif per_group:
            unit_label = "group"
            unit_jp = "グループ"
        else:
            unit_label = "pax"
            unit_jp = "名"
        formula_en = f"({base:,} yen × {qty} {unit_label}) = **{total_str} yen (tax included)**"
        formula_jp = f"（{base:,}円 × {qty}{unit_jp}）＝ **{total_str}円（税込）**"
    else:
        pv_add = 10000 if type_ == "PV" else 0
        subtotal = base * pax + pv_add
        total = round(subtotal * 1.1)
        total_str = f"{total:,}"
        pv_en = " + 10,000 yen private guarantee fee" if type_ == "PV" else ""
        pv_jp = " ＋ 10,000円（プライベート確約料）" if type_ == "PV" else ""
        formula_en = f"({base:,} yen × {pax} pax{pv_en}) × 1.1 tax = **{total_str} yen (tax included)**"
        formula_jp = f"（{base:,}円 × {pax}名{pv_jp}）× 消費税1.1 ＝ **{total_str}円（税込）**"

    # --- 返信文生成 ---
    if mode == "BtoC":
        output = f"""Subject: Booking Request Received – {tour_data['name']}

Dear {name},

Thank you very much for your message.

We have received your booking request for:

★ {tour_data['name']}
{formula_en}

We will coordinate with our guides and get back to you with confirmation.

Please note that once a guide is secured, advance payment will be required.
We will send you a payment link via Square, and the reservation will be confirmed upon receipt of payment.

Best regards,
Kyoko Onodera
Tohoku Local Secret Tours"""

    elif language == "JP":
        output = f"""件名：【ご予約確認】{tour_data['name']}

いつもお世話になっております。

以下の内容でお受けいたします。

★ {tour_data['name']}
{formula_jp}

ツアー実施の約1か月前に、ガイド名を含む最終確認書（PDF）をお送りいたします。
本メールにてツアー終了後の請求予定金額をご案内いたします。

何卒よろしくお願いいたします。

小野寺恭子
株式会社インアウトバウンド東北"""

    else:
        output = f"""Subject: Booking Confirmation – {tour_data['name']}

Dear {name},

Thank you very much for your continued support and for your new booking request.
We are pleased to confirm the reservation as follows:

★ {tour_data['name']}
{formula_en}

We will send a PDF confirmation approximately one month before the tour,
including the guide's name and meeting point details.

Thank you very much for your cooperation.
We look forward to welcoming your clients to Sendai.

Kind regards,
Kyoko Onodera

─────────────────────────────
InOutbound Tohoku Inc.
株式会社インアウトバウンド東北
（Tohoku Local Secret Tours）
Kyoko ONODERA
Island Bldg. 3F 2-1-2
Miyachiyo, Miyagino-ku, Sendai, Miyagi
JAPAN 983-0044
Phone: +81(0)70-5327-0029
Mail: onodera@inoutbound.co.jp
http://www.tohoku-local-secret-tours.jp
─────────────────────────────"""

    # --- 表示 ---
    st.subheader("📤 生成された返信文")
    st.code(output, language="markdown")

    st.subheader("💴 料金内訳")
    if mode == "EXO":
        st.info(f"EXO料金（税込）: {base:,}円 × {qty} = **{total_str}円**")
    else:
        st.info(
            f"税抜単価: {base:,}円 × {pax}名"
            + (f" ＋ PV確約料 10,000円" if type_ == "PV" else "")
            + f" → 税込合計: **{total_str}円**"
        )
