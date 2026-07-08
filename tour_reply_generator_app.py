import streamlit as st

st.set_page_config(page_title="Tour Reply Generator", layout="wide")

st.title("🧭 TLST 返信文作成ツール")

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
    # Attracxi系: タリフの人数区分ごとの税込・1人あたり総額表（1名198,000円
    # 〜4名66,000円/人）を使う。PV/G の区別は適用されない（一律料金）。
    "attracxi_dewa": {
        "name": "Attracxi: Mysteries of the Three Holy Mountains of Dewa",
        "attracxi": True
    },
    "attracxi_hiraizumi": {
        "name": "Attracxi: Hiraizumi Full Day Tour from Sendai",
        "attracxi": True
    },
    "attracxi_samurai": {
        "name": "Attracxi: Master the Way of the Samurai",
        "attracxi": True
    },
    "attracxi_shiogama_matsushima": {
        "name": "Attracxi: Shiogama's Delicacy Trail to Matsushima's Natural Wonders",
        "attracxi": True
    },
    "attracxi_cask": {
        "name": "Attracxi: From Cask to Glass – Tohoku's Craft Journey with Local Cuisine",
        "attracxi": True
    },
    "attracxi_naruko": {
        "name": "Attracxi: Step into Tradition – Craft, Culture, and Hot Springs in Naruko",
        "attracxi": True
    },
}

# Attracxiシリーズ共通の税込・人数区分別1人あたり単価（タリフ記載分）。
# 5名以上はタリフに個別記載がないため、4名単価に近い目安値を暫定使用。
ATTRACXI_GROSS_PER_PERSON = {1: 198000, 2: 99000, 3: 82500, 4: 66000}
ATTRACXI_FALLBACK_PER_PERSON = 60500

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
    # --- 青森・津軽エリア EXO専用ツアー／サービス ---
    "nebuta_spirit_aomori": {
        "name": "EXO Spirit of Aomori Festivals and Lanterns",  # EXO Title
        "supplier_title": "津軽の魂「ねぶた祭り」の原点と現在を巡る",  # Supplier title
        "price": 48000,  # 2名以上/人（税込・プライベート）
        "singlePaxPrice": 88000,  # 1名の場合（例外対応）
        "minPax": 2,  # 例外的に1名可
        "maxPax": 6,
        "startTime": "08:40（青森市内ホテル）",
        "duration": "8.5時間",
        "period": "通年（除外日：8/9-14、12/24-1/5）",
        "priceValidity": "2026年6月1日〜2027年5月30日",
    },
    "audley_aomori_hirosaki_fd": {
        "name": "Audley Aomori & Hirosaki Full Day Guided Tour",  # EXO Title（Supplier titleの記載なし）
        # EXOネット合計・グループ料金（車両費8H＋入場料&ランチ3,820円×人数＋ガイド68,000円）
        "priceTable": {1: 141820, 2: 145640, 3: 167460, 4: 179280, 5: 194900, 6: 194900},
        "minPax": 1,
        "maxPax": 6,
        "startTime": "09:00（弘前または青森市内ホテル）",
        "duration": "8時間",
        "period": "通年（除外日：8/9-14、12/24-1/5）",
        "priceValidity": "Till Dec 2026",
    },
    "aomori_half_day_guide": {
        "name": "AOMORI HALF DAY GUIDE TOUR",  # EXO Title（Supplier titleの記載なし）
        "price": 30000,  # 2名以上/人（税込）
        "singlePaxPrice": 58000,  # 1名の場合（例外対応）
        "minPax": 1,  # 例外的に1名可、通常2名〜
        "maxPax": 7,
        "startTime": "09:00",
        "duration": "4時間（9:00-13:00）",
        "period": "通年（除外日：8/9-14、12/24-1/5）",
    },
    "aomori_guide_assistant_mg": {
        "name": "Aomori Guide Assistant / Meet & Greet",  # EXO Title
        "supplier_title": "Aomori Guide Assistant",  # Supplier title
        "price": 19800,  # グループ（税込）
        "perGroup": True,
        "minPax": 1,
        "maxPax": 6,
        "note": "新青森駅新幹線プラットフォームでお出迎え、ホテルまでチェックインサポート。2時間ガイド・ガイド改札入場料金・ガイド交通費込み",
    },
    "aomori_guide_half_day": {
        "name": "Aomori Guide Half Day",  # EXO Title
        "supplier_title": "Aomori Guide（半日）",  # Supplier title
        "price": 35000,  # グループ（税込・ガイド交通費込、4時間まで）
        "perGroup": True,
        "minPax": 1,
        "maxPax": 6,
        "note": "半日（4時間まで）",
    },
    "aomori_guide_full_day": {
        "name": "Aomori Guide Full Day",  # EXO Title
        "supplier_title": "Aomori Guide（終日）",  # Supplier title
        "price": 68000,  # グループ（税込・ガイド交通費込、8時間まで）
        "perGroup": True,
        "minPax": 1,
        "maxPax": 6,
        "note": "終日（8時間まで）",
    },
}

# --- 参考情報：弘前・津軽エリア 貸切車両料金表（税込）---
# 正式料金は発着場所・走行距離により都度確認が必要
hirosaki_vehicle_rates = {
    "小型車": {
        "hours": {1: 8800, 2: 17600, 3: 26200, 4: 35000, 5: 43800, 6: 56000, 7: 61000, 8: 70000},
        "extra_hour": 8800,
    },
    "ジャンボタクシー": {
        "hours": {1: 13000, 2: 26000, 3: 39000, 4: 51800, 5: 64800, 6: 77800, 7: 80800, 8: 103600},
        "extra_hour": 13000,
    },
    "アルファード": {
        "hours": {1: 11000, 2: 22000, 3: 33000, 4: 44000, 5: 55000, 6: 66000, 7: 77000, 8: 88000},
        "extra_hour": 11000,
    },
}

# --- 参考情報：ホテル ---
hotels = {
    "blossom_hotel_hirosaki": {
        "name": "Blossom Hotel Hirosaki",  # EXO Title / Supplier title 共通
        "note": "さくら祭り・夏祭り期間限定営業",
        "rooms": {
            "Single（Standard Double）": {"price": 40000, "size": "17㎡"},
            "Single（Deluxe Double）": {"price": 42000, "size": "18㎡"},
            "Standard Twin": {"price": 60000, "size": "22.5㎡"},
            "Deluxe Twin": {"price": 64000, "size": "29㎡"},
            "Suite": {"price": 120000, "size": "35㎡", "maxPax": 3},
        },
        "breakfast": 2000,  # 円/人（税抜）
        "operatingPeriods": {
            "さくら期間": "4月12日〜5月5日",
            "夏祭り期間": "8月1日〜8月8日",
        },
        "cancellationPolicy": {
            "60日前まで": "無料",
            "60〜14日前": "30%",
            "13〜7日前": "40%",
            "6〜2日前": "50%",
            "前日・当日": "100%",
        },
        "cancellationNote": "EXOと弊社間は30日前確定が必要",
        "pricing2027": {
            "base": "基本料金から10%増",
            "peakDates": "さらに10%増（合計20%増）：①8月2日・8月7日（ねぶた初日・最終日）②4月3週・4週の土曜日（満開想定）",
        },
        "breakfastNote": "和食のお弁当が部屋食でお部屋に運ばれる。繁忙期のため食事制限対応不可",
        "childPolicy": "添い寝：未就学児6歳まで（朝食は大人と同額）。大人2名につき1名添い寝可",
        "priceValidity": "2027年5月5日まで",
    },
}


# --- 料金計算ロジック（料金表・返信文作成ツールで共用） ---
def calculate_price(mode, tour_data, pax, type_):
    """Returns (total, formula_jp, formula_en, warning)"""
    base = tour_data.get("price", 0)
    warning = None

    if tour_data.get("attracxi"):
        # Attracxiシリーズはタリフの人数区分別・税込1人あたり総額表を使う。
        # AGT/BtoC/PV・Gの違いによる加算はない（一律料金）。
        unit = ATTRACXI_GROSS_PER_PERSON.get(pax, ATTRACXI_FALLBACK_PER_PERSON)
        total = unit * pax
        total_str = f"{total:,}"
        formula_en = f"{unit:,} yen × {pax} pax = **{total_str} yen (tax included)**"
        formula_jp = f"{unit:,}円 × {pax}名 ＝ **{total_str}円（税込）**"
        return total, formula_jp, formula_en, warning

    if mode == "EXO":
        per_vehicle = tour_data.get("perVehicle", False)
        per_group = tour_data.get("perGroup", False)
        qty = 1 if (per_vehicle or per_group) else pax

        price_table = tour_data.get("priceTable")
        single_pax_price = tour_data.get("singlePaxPrice")
        min_pax = tour_data.get("minPax")
        max_pax = tour_data.get("maxPax")

        if min_pax and pax < min_pax and not (single_pax_price and pax == 1):
            warning = f"⚠️ このツアーの対応人数は{min_pax}〜{max_pax or '-'}名です。人数をご確認ください。"
        elif max_pax and pax > max_pax:
            warning = f"⚠️ このツアーの対応人数は{min_pax or 1}〜{max_pax}名です。人数をご確認ください。"

        if price_table:
            lookup_pax = min(pax, max(price_table.keys()))
            total = price_table[lookup_pax]
            total_str = f"{total:,}"
            formula_en = f"EXO net group rate for {pax} pax = **{total_str} yen (tax included)**"
            formula_jp = f"{pax}名時の EXOネット・グループ料金 ＝ **{total_str}円（税込）**"
        elif single_pax_price and pax == 1:
            total = single_pax_price
            total_str = f"{total:,}"
            formula_en = f"1 pax special rate = **{total_str} yen (tax included)**"
            formula_jp = f"1名特別料金 ＝ **{total_str}円（税込）**"
        else:
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

    return total, formula_jp, formula_en, warning


# ============================================================
# 📊 TLST料金表（社内共有用・料金をすぐ確認できる早見表）
# ============================================================
st.header("📊 TLST料金表")
st.caption("社内共有用の料金早見表です。プルダウンを選ぶとすぐ下に料金が表示されます。")

pt_col1, pt_col2, pt_col3 = st.columns(3)

with pt_col1:
    pt_mode = st.selectbox("返信タイプ", ["AGT", "EXO", "BtoC"], key="pt_mode")

with pt_col2:
    pt_pax = st.number_input("人数", min_value=1, value=2, key="pt_pax")

with pt_col3:
    if pt_mode != "EXO":
        pt_type = st.selectbox("タイプ", ["G", "PV"], key="pt_type")
    else:
        pt_type = "G"

pt_tour_list = exo_tours if pt_mode == "EXO" else tours
pt_tour = st.selectbox(
    "ツアーを選択",
    list(pt_tour_list.keys()),
    format_func=lambda x: pt_tour_list[x]["name"],
    key="pt_tour"
)
pt_tour_data = pt_tour_list[pt_tour]
_pt_supplier_title = pt_tour_data.get("supplier_title")
if _pt_supplier_title and _pt_supplier_title != pt_tour_data["name"]:
    st.caption(f"社内タイトル（Supplier title）: {_pt_supplier_title}")
if pt_tour_data.get("attracxi"):
    st.caption("ℹ️ Attracxiシリーズはタイプ（G/PV）に関わらず一律料金です。")

pt_total, pt_formula_jp, pt_formula_en, pt_warning = calculate_price(pt_mode, pt_tour_data, pt_pax, pt_type)
if pt_warning:
    st.warning(pt_warning)
st.info(f"💴 料金: {pt_formula_jp}")

st.divider()

# ============================================================
# ✉️ 返信文作成ツール
# ============================================================
st.header("✉️ 返信文作成ツール")

# --- 設定エリア ---
col1, col2, col3, col4 = st.columns(4)

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

tour_list = exo_tours if mode == "EXO" else tours

# ツアー名が長いため専用の全幅行に配置
tour = st.selectbox(
    "ツアーを選択",
    list(tour_list.keys()),
    format_func=lambda x: tour_list[x]["name"]
)
_supplier_title = tour_list[tour].get("supplier_title")
if _supplier_title and _supplier_title != tour_list[tour]["name"]:
    st.caption(f"社内タイトル（Supplier title）: {_supplier_title}")
if tour_list[tour].get("attracxi"):
    st.caption("ℹ️ Attracxiシリーズはタイプ（G/PV）に関わらず一律料金です。")

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

    total, formula_jp, formula_en, warning = calculate_price(mode, tour_data, pax, type_)
    if warning:
        st.warning(warning)

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
    if tour_data.get("attracxi"):
        st.info(f"Attracxiシリーズ一律料金（税込）: {formula_jp}")
    elif mode == "EXO":
        st.info(f"EXO料金（税込）: {formula_jp}")
    else:
        st.info(
            f"税抜単価: {tour_data.get('price', 0):,}円 × {pax}名"
            + (f" ＋ PV確約料 10,000円" if type_ == "PV" else "")
            + f" → 税込合計: **{total:,}円**"
        )

# --- 参考情報：貸切車両料金表 ---
with st.expander("📎 参考情報：弘前・津軽エリア 貸切車両料金表（税込）"):
    st.caption("正式料金は発着場所・走行距離により都度確認が必要です。")
    for car_type, rates in hirosaki_vehicle_rates.items():
        hours_str = " / ".join(
            f"{h}H: {price:,}円" for h, price in rates["hours"].items()
        )
        st.markdown(f"**{car_type}**  \n{hours_str}  \n以降1時間ごと: {rates['extra_hour']:,}円")

# --- 参考情報：ホテル ---
with st.expander("📎 参考情報：ホテル"):
    for hotel in hotels.values():
        st.markdown(f"### {hotel['name']}")
        st.caption(hotel["note"])

        st.markdown("**客室料金（税抜・1室あたり）**")
        for room_name, room in hotel["rooms"].items():
            max_pax_str = f"・最大{room['maxPax']}名" if "maxPax" in room else ""
            st.markdown(f"- {room_name}: {room['price']:,}円 / {room['size']}{max_pax_str}")
        st.markdown(f"- 朝食: {hotel['breakfast']:,}円/人（税抜）")
        st.caption(hotel["breakfastNote"])

        st.markdown("**営業期間**")
        for period_name, period in hotel["operatingPeriods"].items():
            st.markdown(f"- {period_name}: {period}")

        st.markdown("**キャンセルポリシー**")
        for timing, rate in hotel["cancellationPolicy"].items():
            st.markdown(f"- {timing}: {rate}")
        st.caption(hotel["cancellationNote"])

        st.markdown("**2027年以降の料金**")
        st.markdown(f"- {hotel['pricing2027']['base']}")
        st.markdown(f"- {hotel['pricing2027']['peakDates']}")

        st.markdown(f"**子供ポリシー**: {hotel['childPolicy']}")
        st.markdown(f"**料金有効期限**: {hotel['priceValidity']}")
