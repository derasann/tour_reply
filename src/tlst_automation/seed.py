"""One-off seed script: populates guides/agents/tours/stopovers from the
existing hand-kept references (Sheet2 of 0625Hungry.xlsx, KNOWLEDGE.md,
pricing.py, and the Hungry Samurai sample guide request).

Safe to re-run: upserts are keyed on name, so re-running just refreshes
values rather than duplicating rows.

Usage:
    PYTHONPATH=src python -m tlst_automation.seed
"""

from __future__ import annotations

import sqlite3

from . import db
from .master import Agent, Guide, Stopover, Tour
from .models import ItineraryStop
from .pricing import AGT_NET_PRICES, EXO_GROSS_PRICES

# area, tour name, guide, agent company -- from Sheet2 of 0625Hungry.xlsx
AREA_TOUR_GUIDE_AGENT = [
    ("仙台", "Back-alley Bar Hopping in Sendai", "麿律子", "BtoC"),
    ("仙台", "Back-alley Night Izakaya Hopping in Sendai", "玉田千恵", "Boutique Japan"),
    ("仙台", "Hungry Samurai: Sendai Food & Culture Tour", "志賀理恵", "byFood"),
    ("仙台", "Hungry Samurai : Sendai Food & Culture day Tour (version with cab)", "本田舞", "Essential Japan Travel"),
    ("仙台", "Foodie Delight: Culinary Walking Tour -150 min quick tour-", "海野明実", "Hidden Japan"),
    ("塩竈", "Foodie tour in Shiogama", "熊坂雪江", "Inside Japan Tours"),
    ("塩竈", "Shiogama's 10 Tasting Treasures: Savoring Sweets, Seafood & Sake", "横山由美", "近畿日本ツーリスト"),
    ("塩竈・松島", "Shiogama's Delicacy Trail to Matsushima's Natural Wonders", "佐藤美和", "Harbour City Travel"),
    ("東松島", "Oyster Paradise Matsushima", "中村智子", "リージェンシー・グループ"),
    ("東松島", "Oyster Fisherman's Cruise & Seasonal Feast (version with JR train)", "奥山茂雄", "Amala Destinations"),
    ("東松島", "Cruise with an oyster fisherman for an all-you-can-eat oyster, visit picturesque Matsushima (version with JR and cab)", "佐々裕子", ""),
    ("塩竈", "【Miyagi・Shiogama】Spirit of Japanese Sake", "横山由美", ""),
    ("松島", "Kimono Walking Tour of Matsushima", "西谷", "JTB 仙台"),
    ("鳴子", "Earth-friendly art: Bamboo straw workshop (with lunch)", "後藤", "JTB-AUS"),
]

OTHER_AGENT_COMPANIES = [
    "OKUNI合同会社", "River Bend Travel Inc.", "Tripadvisor (Viator)", "日本旅行東北",
    "EXO Travel Japan 株式会社", "BOJ", "ロッテ観光株式会社", "みちのりトラベル東北",
    "See Asia Tours Ltd", "JTB GMT", "じゃらん", "Katsume", "第一広告社",
    "Wayfairer Travel", "THE J TEAM Co. Ltd.", "JOYOJ", "HIS東北",
]

# From the Hungry Samurai (0625) guide request itinerary sample.
SAMPLE_STOPOVERS = [
    Stopover(None, "S-PAL仙台東館 伊達のこみち 藤原屋みちのく酒紀行", "S-PAL仙台東館 2階", "022-357-0209", 200, "tasting", "地酒自販機試飲体験 @200円"),
    Stopover(None, "仙台朝市 ころっけ屋", "仙台市青葉区中央4丁目3-27", "022-267-1569", 200, "food", "ころっけ @〜200円"),
    Stopover(None, "鯛きち 名掛丁店", "仙台市青葉区中央2-1-30 (須田ビル1F)", "022-224-7233", 250, "food", "たいやき @〜250円"),
    Stopover(None, "三瀧山不動院", "青葉区中央2-5-7", "022-263-4113", 0, "sightseeing", "三滝不動尊立寄り"),
    Stopover(None, "お茶の井ヶ田仙台中央本店", "宮城県仙台市青葉区中央2-5-9", "022-261-1351", 550, "food", "緑茶/ずんだシェイク等 @550"),
    Stopover(None, "玉澤総本店 クリスロード店（晴れの菓）", "青葉区中央2-3-19", "022-222-5854", 120, "food", "黒砂糖まんじゅう @120円"),
    Stopover(None, "阿部蒲鉾店 本店", "青葉区中央2-3-18", "022-221-7121", 220, "food", "笹かま購入 @220円"),
    Stopover(None, "藤崎 地下1階", "仙台市青葉区一番町3-2-17", "022-261-5111", 300, "food", "量り売り菓子 @300円"),
    Stopover(None, "そばの神田・仙台っ子等", "仙台市青葉区一番町2-4-17", "022-265-7966", 800, "food", "そば・ラーメン等 @800円（ガイド分+1）"),
    Stopover(None, "瑞鳳殿", "青葉区霊屋下23-2", "022-262-6250", 570, "sightseeing", "拝観料 @570円 + @410円 + ガイド分"),
    Stopover(None, "仙台城跡", "青葉区天守台青葉城跡", "", 0, "sightseeing", "見学"),
]

# Itinerary template for the Hungry Samurai guide request, taken verbatim
# from templates/guide_request_template.pptx (the real 0625 example).
HUNGRY_SAMURAI_ITINERARY = [
    ItineraryStop("10:00", "仙台駅２階ステンドグラス前", "", "", "集合場所"),
    ItineraryStop(
        "10:05-10:15", "S-PAL仙台東館 伊達のこみち　藤原屋みちのく酒紀行",
        "地酒自販機試飲体験 @200円　× 1", "現金", "S-PAL仙台東館 2階 TEL:022-357-0209",
    ),
    ItineraryStop(
        "10:20-10:30", "仙台朝市 ころっけ屋",
        "ころっけ @〜200円　× 2", "現金", "仙台市青葉区中央4丁目3-27 TEL:022-267-1569",
    ),
    ItineraryStop(
        "10:40-10:50", "鯛きち ※名掛丁店",
        "たいやき @〜250円　× 2", "現金", "仙台市青葉区中央2-1-30 (須田ビル1F) TEL:022-224-7233",
    ),
    ItineraryStop("11:00-11:10", "三瀧山不動院", "三滝不動尊立寄り", "", "中央2-5-7 TEL:022-263-4113"),
    ItineraryStop(
        "11:15-11:25", "お茶の井ヶ田仙台中央本店",
        "緑茶/ずんだシェイク等 @550 x 2", "現金", "宮城県仙台市青葉区中央2-5-9 TEL: 022-261-1351",
    ),
    ItineraryStop(
        "11:30-11:35", "玉澤総本店 クリスロード店（晴れの菓）",
        "黒砂糖まんじゅう @120円× 2", "現金", "青葉区中央2-3-19 TEL: 022-222-5854",
    ),
    ItineraryStop(
        "11:40-11:45", "阿部蒲鉾店 本店",
        "笹かま購入 @220円　× 2", "現金", "青葉区中央2-3-18 TEL: 022-221-7121",
    ),
    ItineraryStop(
        "11:50-12:00", "藤崎　地下1階",
        "ラウンド量り売り菓子 ＠300 × 2", "現金", "仙台市青葉区一番町3-2-17 TEL：022-261-5111（代表）",
    ),
    ItineraryStop(
        "12:00-13:00", "ランチ　そばの神田・仙台っ子等",
        "そば・ラーメン等 @800 × 2＋１", "現金", "仙台市青葉区一番町2-4-17 TEL：Tel.022-265-7966",
    ),
    ItineraryStop("13:00-13:20", "タクシー　藤崎前 - 瑞宝殿", "1,500円/台 × 1", "現金", "タクシー"),
    ItineraryStop("13:20-14:20", "瑞鳳殿", "@570円 + @410円 + ガイド分", "現金", "青葉区霊屋下23-2 TEL 262-6250"),
    ItineraryStop(
        "14:20-14:45", "タクシー瑞鳳殿 - 仙台城跡\n拝観中に配車依頼して下さい",
        "2,000円 /台 × 1", "現金", "参考）第一交通：022-236-1221　無線タクシー：0570-061-000",
    ),
    ItineraryStop("14:45-15:30", "仙台城跡　見学", "", "", "青葉区天守台青葉城跡"),
    ItineraryStop(
        "15:30-15:50", "タクシー仙台城跡 -青葉山駅",
        "2,000円 /台 × 1", "現金", "参考）第一交通：022-236-1221　無線タクシー：0570-061-000",
    ),
    ItineraryStop("16:00", "仙台駅到着　解散", "おつかれさまでした", "", ""),
]

# name, area -- extracted from Tariff_2025_TLST.pdf (tour catalogue), tours
# not already covered by AREA_TOUR_GUIDE_AGENT / pricing.py.
TARIFF_TOURS = [
    ("Nightlife & Tradition: Hachinohe Yokocho Izakaya Experience（AOMORI)", "八戸市 (青森)"),
    ("Back-alley Bar Hopping in Miyako (Iwate)", "宮古市 (岩手)"),
    ("Bar Hopping in Tsuruoka (Yamagata)", "鶴岡市 (山形)"),
    ("Dake Onsen Bar Hopping Tour (Fukushima)", "岳温泉 (福島)"),
    ("Izakaya and Japanese “Snack Bar” Tour in Kakunodate (Akita)", "角館 (秋田)"),
    ("Shiogama's Delicacy Trail to Matsushima's Natural Wonders", "塩竈市・松島町 (宮城)"),
    ("Fish & Feast with local fisherman!  Fishing, Local Traditions, and BBQ Lunch", "利府町 (宮城)"),
    ("Attracxi: Mysteries of the Three Holy Mountains of Dewa", "出羽三山 (山形)"),
    ("Hiraizumi Full Day Tour from Sendai", "平泉町 (岩手)"),
    ("Attracxi: Master the Way of the Samurai", "村山市 (山形)"),
    ("Attracxi: From Cask to Glass – Tohoku's Craft Journey with Local Cuisine", "仙台市秋保 (宮城)"),
    ("Attracxi: Step into Tradition: Craft, Culture, and Hot Springs in Naruko", "鳴子 (宮城)"),
    ("Kyoto Sensu Painting & Tosenkyo Experience", "京都"),
    ("Meet a Buddhist Monk", "京都"),
    ("Exclusive To-ji Heritage Tour – Private Journey Through Kyoto's Hidden Treasures", "京都"),
    ("Exclusive Meditation at a Hidden Temple - A Private Retreat at Ryosokuin", "京都"),
    ("The Four Spirits of Zen - A Private Journey Through Kyoto's Timeless Wisdom", "京都"),
]


def seed_all(conn: sqlite3.Connection) -> None:
    existing_guides = {g.name for g in db.list_guides(conn)}
    existing_agents = {a.company_name for a in db.list_agents(conn)}
    existing_tours = {t.name for t in db.list_tours(conn)}
    existing_stopovers = {s.name for s in db.list_stopovers(conn)}

    for area, tour_name, guide_name, agent_name in AREA_TOUR_GUIDE_AGENT:
        if guide_name and guide_name not in existing_guides:
            db.upsert_guide(conn, Guide(id=None, name=guide_name, area=area))
            existing_guides.add(guide_name)
        if tour_name not in existing_tours:
            category = "bar_hop" if "Bar Hop" in tour_name or "Izakaya" in tour_name else "food"
            db.upsert_tour(conn, Tour(id=None, name=tour_name, area=area, category=category))
            existing_tours.add(tour_name)
        if agent_name and agent_name not in existing_agents:
            db.upsert_agent(conn, Agent(id=None, company_name=agent_name))
            existing_agents.add(agent_name)

    for agent_name in OTHER_AGENT_COMPANIES:
        if agent_name not in existing_agents:
            db.upsert_agent(conn, Agent(id=None, company_name=agent_name))
            existing_agents.add(agent_name)

    for tour_name, price in {**AGT_NET_PRICES, **EXO_GROSS_PRICES}.items():
        if tour_name not in existing_tours:
            category = "bar_hop" if "Bar Hop" in tour_name or "Izakaya" in tour_name else "food"
            db.upsert_tour(conn, Tour(id=None, name=tour_name, category=category))
            existing_tours.add(tour_name)

    for stopover in SAMPLE_STOPOVERS:
        if stopover.name not in existing_stopovers:
            db.upsert_stopover(conn, stopover)
            existing_stopovers.add(stopover.name)

    for tour_name, area in TARIFF_TOURS:
        if tour_name not in existing_tours:
            category = "bar_hop" if "Bar Hop" in tour_name or "Izakaya" in tour_name else "food"
            db.upsert_tour(conn, Tour(id=None, name=tour_name, area=area, category=category))
            existing_tours.add(tour_name)

    if not db.list_tour_itinerary_variants(conn, "Hungry Samurai: Sendai Food & Culture Tour"):
        db.save_tour_itinerary_variant(
            conn, "Hungry Samurai: Sendai Food & Culture Tour", "0625実例（オリジナル）", HUNGRY_SAMURAI_ITINERARY
        )

    # Corrections/additions confirmed from real guide-request & confirmation
    # examples (0714 barhopping, 0722 Hungry Samurai). Guide personal
    # contact numbers are intentionally NOT hardcoded here since this repo
    # is public -- add them locally via the マスタ管理 page after seeding.
    tours_by_name = {t.name: t for t in db.list_tours(conn)}
    for tour_name in ("Back-alley Bar Hopping in Sendai", "Back-alley izakaya Bar Hopping in Sendai"):
        tour = tours_by_name.get(tour_name)
        if tour is not None:
            db.upsert_tour(
                conn,
                Tour(
                    id=tour.id,
                    name=tour.name,
                    area=tour.area or "仙台",
                    category="bar_hop",
                    meeting_point_en="McDonald's Sendai Aobadori",
                    meeting_point_jp="マクドナルド仙台青葉通り",
                    inclusions=["3 drinks and 3 dishes in total at 3 Izakayas (Mon-Thu; 2 Izakayas Fri/Sat/Sun/holidays)"],
                    exclusions=["Additional food and drink charges, etc."],
                )
            )


def main() -> None:
    conn = db.connect()
    seed_all(conn)
    print(
        f"Seeded: {len(db.list_guides(conn))} guides, "
        f"{len(db.list_agents(conn))} agents, "
        f"{len(db.list_tours(conn))} tours, "
        f"{len(db.list_stopovers(conn))} stopovers."
    )


if __name__ == "__main__":
    main()
