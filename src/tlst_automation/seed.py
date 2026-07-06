"""One-off seed script: populates guides/agents/tours/stopovers from the
existing hand-kept references (Sheet2 of 0625Hungry.xlsx, KNOWLEDGE.md,
pricing.py, and the Hungry Samurai sample guide request).

Safe to re-run: upserts are keyed on name, so re-running just refreshes
values rather than duplicating rows.

Usage:
    PYTHONPATH=src python -m tlst_automation.seed
"""

from __future__ import annotations

import re
import sqlite3

from . import db
from .master import Agent, Guide, MeetingPoint, Stopover, Tour
from .models import ItineraryStop
from .pricing import AGT_NET_PRICES, EXO_GROSS_PRICES
from .rules import tour_names_match

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



# name (as printed in the tariff), inclusions, exclusions, meeting_point_text
# -- extracted from Tariff_2025_TLST.pdf ("Included/Not included in price" fields).
TARIFF_INCLUSIONS_EXCLUSIONS = [
    (
        'Back-alley Night Izakaya Hopping in Sendai',
        ['Guide fee', 'food & drink（3 drinks & ３dishes)', 'insurance'],
        ['Any additional meals and drinks', 'transport to/from meeting point', 'anything not listed as included'],
        'McDonald’s Sendai Aobadori2 Chome-5-1 Ichibancho, Aoba Ward, Sendai, Miyagi 980-0811',
    ),
    (
        'Bar Hopping in Koubuncho VEG',
        ['Guide fee', 'food & drink -two different taverns of different styles', 'enjoying one drink and one plate of local cuisine at each', 'insurance'],
        ['Any additional meals and drinks', 'transport to/from meeting point', 'anything not listed as included'],
        'Hotel Grand Terrace Kokubuncho2-2-2, Kokubuncho, Aoba Ward, Sendai, Miyagi 980-0803',
    ),
    (
        'BaNightlife& Tradition: Hachinohe Yokocho Izakaya Experience（AOMORI)',
        ['Walking tour of alleyways', 'Visit to three different izakayasof different styles', 'enjoying one drink and some plates of local cuisine at each', 'English speaking guide to teach you the tips and tricks of navigating a local izakaya!', 'Insurance'],
        ['Any additional meals and drinks', 'anything not listed as included'],
        'Hachinohe Portal Museum “Hacchi”',
    ),
    (
        'Back-alley Bar Hopping in Miyako (Iwate)',
        ['・English speaking guide・2 plates and 2 drinks at each izakaya'],
        ['Any additional meals and drinks', 'transport to/from meeting point', 'anything not listed as included'],
        'Miyako Station',
    ),
    (
        'Bar Hopping in Tsuruoka (Yamagata)',
        ['Walking tour of Bunka-yokochoand Iroha-yokochoalleyways', 'Visit to three different izakayasof different styles', 'enjoying one drink and one plate of local cuisine at each', 'English speaking guide to teach you the tips and tricks of navigating a local izakaya!', 'Insurance'],
        ['Any additional meals and drinks', 'anything not listed as included'],
        'Sushi & TempraShibaraku',
    ),
    (
        'Dake Onsen Bar Hopping Tour (Fukushima)',
        ['Visit to three different izakayasof different styles', 'enjoying one drink and one plate of local cuisine at each', 'English speaking guide to teach you the tips and tricks of navigating a local izakaya!', 'Insurance'],
        ['Any additional meals and drinks', 'anything not listed as included'],
        'Dake Onsen',
    ),
    (
        'Izakaya and Japanese “Snack Bar” Tour in Kakunodate (Akita)',
        ['Guide fee', 'food & drink -two different taverns of different styles', 'enjoying one drink and one plate of local cuisine at each', 'insurance'],
        ['Any additional meals and drinks', 'transport to/from meeting point', 'anything not listed as included'],
        'Tachimachi Pocket Park 39-3, Iwase-machi, Kakunodate, Senboku-shi',
    ),
    (
        'Hungry Samurai: Sendai Food & Culture day Tour (version with cab)',
        ['Sake tasting', 'croquettes', 'taiyaki', 'tea', 'sasakamama', 'monaka', 'sweets by weight', 'Zuihoudenentrance fee', 'cab fare (2 sections)', 'English-speaking guide', 'insurance'],
        ['Transportation to the meeting place', "anythingnot included in the above 'included' list"],
        '',
    ),
    (
        'Foodie Delight: Culinary Walking Tour -150 min quick tour-',
        ['Sake tasting', 'croquettes or dumplings', 'taiyaki', 'zunda shake', 'sasakamama', 'monaka', 'candies by weighthamburgers (or standing soba noodles)', 'English speaking guide', 'Insurance'],
        ['Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        "Shiogama's 10 Tasting Treasures: Savoring Sweets, Seafood & Sake",
        ['JR train and taxi fare', 'Seafood breakfast at Shiogama Wholesale Fish Market (A maximum of 3 toppings are complimentary)', 'Walking tour of Shiogama', 'Gourmet items : Miso gelato', 'local sweets', 'salt cookie and cake', 'dorayaki', 'sake tasting', 'candy', 'another sake tasting', 'tea tasting. English speaking guide', 'insurance'],
        ['Any additional toppings will incur a guest surcharge on fish market', 'Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        'Shiogama’s Delicacy Trail to Matsushima’s Natural Wonders',
        ['JR train and taxi fare', 'Sightseeing boat boarding fee', 'Morning Coffee', 'Walking tour of Shiogama', 'Gourmet items : gelato', 'local sweets', 'salt cookie', 'dorayaki', 'sake tasting', 'Seafood bowl for lunch', 'Kanrantei entrance fee and macha set', 'English speaking guide', 'Insurance'],
        ['Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        'Oyster Fisherman’s Cruise & Seasonal Feast (version with JR train)',
        ['JR train and taxi fare', 'Cruise of Matsushima Bay', '90-minute pleasure boat ride (oyster farming tour and Matsushima Bay cruise)', 'Seafood lunch at a local restaurant', 'English speaking Guide', 'Insurance'],
        ['Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        'Cruise with an oyster fisherman for an all-you-can-eat oyster, visit picturesque Matsushima (version with JR and cab)',
        ['JR train and taxi fare', 'Cruise of Matsushima Bay', '90-minute pleasure boat ride (oyster farming tour and Matsushima Bay cruise)', 'All you can eat oyster lunch', 'Kanrantei entrance fee', 'matcha set', 'English speaking Guide', 'Insurance'],
        ['Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        'Fish & Feast with local fisherman! Fishing, Local Traditions, and BBQ Lunch',
        ['English-speaking guide', 'JR train fare', 'Taxi fare', '90-minute fishing experience (including traditional net fishing and rod fishing)', 'Local seafood set meal', 'Insurance'],
        ['Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        'Attracxi: Mysteries of the Three Holy Mountains of Dewa',
        ['Chartered taxi', 'English guide fee', 'Yamabushi guide', 'Shojin Ryori (vegetarian temple cuisine)', 'Insurance'],
        ['Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        'Hiraizumi Full Day Tour from Sendai',
        ['Chartered taxi', 'English guide fee', 'Genbikei Dango', 'Admission to Chuson-ji Temple and lunch', 'Geibikei Gorge boat ride', 'Insurance'],
        ['Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        'Master the Way of the Samurai',
        ['Chartered taxi', 'English guide fee', 'Iaido program', 'lunch', 'Insurance'],
        ['Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        'Shiogama’s Delicacy Trail to Matsushima’s Natural Wonders',
        ['Chartered taxi', 'English guide fee', 'Coffee at Shiogama Wholesale Fish Market', 'Walking tour of Shiogama', '3 Gourmet items : gelato', 'Dorayaki', 'Sake tasting', 'or local traditional sweets', 'Japanese-tea’s tea bag', 'Sushi for lunch', 'Sightseeing boat boarding fee', 'Entsu-in Temple entrance fee', 'Insurance'],
        ['Any additional toppings will incur a guest surcharge on fish market', 'Any additional meals/drinks', "anything not included in the above 'included' list"],
        '',
    ),
    (
        'From Cask to Glass –Tohoku’s Craft Journey with Local Cuisine',
        ['Brewery/distillery/winery tours (one drink included at each location)', 'Pairing dinner', 'Guide', 'Private vehicle', 'Insurance'],
        ['Any additional meals or drinks', 'Anything not listed in the “Included” section above'],
        '',
    ),
    (
        'Step into Tradition: Craft, Culture, and Hot Springs in Naruko(Miyagi)',
        ['Lacquered bamboo straw workshop', 'Lacquered bamboo straw', 'Local lunch (vegetarian available)', 'Guide', 'KokeshiDoll Painting Experience', 'Insurance'],
        ['Any additional meals and drinks', 'Anything not included in the above included list'],
        '',
    ),
    (
        'Kyoto Sensu Painting & TosenkyoExperience',
        ['Sensu Fan Painting Experience (your hand-painted fan will be shipped to your home) + TosenkyoGame*Includes private transportation from and back to your hotel', 'Insurance'],
        ['Additional food and beverage costs', 'other items not included in "What\'s included in the price"'],
        '',
    ),
    (
        'Meet a Buddhist Monk',
        ['Private Zazen Meditation + Matcha & Sweets Break + Sutra Copying Experience*Includes private transportation from and back to your hotel', 'Insurance'],
        ['Additional food and beverage costs', 'other items not included in "What\'s included in the price"'],
        '',
    ),
    (
        'Exclusive To-ji Heritage Tour –Private Journey Through Kyoto’s Hidden Treasures',
        ['Private Viewing of the Five-Story Pagoda (normally closed to the public) + Kondo (Main Hall) + Kodo (Lecture Hall) + Shoshibo(non-public area) + Kanchi-in + Shakyo(Sutra Copying) + Limited-Edition Goshuin(Temple Seal) *Includes private transportation from and back to your hotel', 'Insurance'],
        ['Additional food and beverage costs', 'other items not included in "What\'s included in the price"'],
        '',
    ),
    (
        'Exclusive Meditation at a Hidden Temple -A Private Retreat at Ryosokuin',
        ['Private Seated Meditation + Walking Meditation in a Temple Garden*Includes private transportation from and back to your hotel', 'Insurance'],
        ['Additional food and beverage costs', 'other items not included in "What\'s included in the price"'],
        '',
    ),
    (
        'The Four Spirits of Zen -A Private Journey Through Kyoto’s Timeless Wisdom',
        ['Private Meditation Experience + Walking Meditation in a Garden + Sutra Copying + Japanese Tea Ceremony *Includes private transportation from your hotel', 'all in-experience transfers', 'and return service to your hotel', 'Insurance'],
        ['Additional food and beverage costs', 'other items not included in "What\'s included in the price"'],
        '',
    ),
]

def _matching_tour_names(tariff_title: str, existing_names: set[str]) -> list[str]:
    """Tariff PDF titles have OCR-ish glitches and existing tour names have
    their own spelling variants (seeded from several sources), so match by
    normalized substring (rules.tour_names_match) rather than requiring an
    exact string match."""
    matches = []
    for name in existing_names:
        if tour_names_match(tariff_title, name):
            matches.append(name)
    return matches


def _meeting_point_name(meeting_point_text: str) -> str:
    """First chunk of the tariff's meeting point text, before the address/
    URL, as a short label for the MeetingPoint master."""
    if not meeting_point_text:
        return ""
    head = re.split(r"[,\d]", meeting_point_text, maxsplit=1)[0]
    return head.strip() or meeting_point_text.strip()


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

    # Inclusions/Exclusions/meeting-point text straight from the tariff, so
    # Booking Confirmations default to the official wording rather than
    # freehand text. Applied by fuzzy name match since the tariff PDF's
    # titles and the tour master's names come from different sources and
    # don't always match character-for-character.
    tours_by_name = {t.name: t for t in db.list_tours(conn)}
    matched_meeting_points: dict[str, str] = {}
    for tariff_title, inclusions, exclusions, meeting_point_text in TARIFF_INCLUSIONS_EXCLUSIONS:
        matches = _matching_tour_names(tariff_title, set(tours_by_name.keys()))
        if not matches:
            # No existing tour master entry matched -- keep the tariff
            # entry available as a new one rather than silently dropping it
            # (e.g. the Attracxi-priced variant of a tour that otherwise
            # only exists in its standard-priced form).
            db.upsert_tour(
                conn,
                Tour(
                    id=None, name=tariff_title, category="other",
                    inclusions=inclusions, exclusions=exclusions,
                ),
            )
            tours_by_name = {t.name: t for t in db.list_tours(conn)}
            matches = [tariff_title]
        for name in matches:
            tour = tours_by_name[name]
            if tour.inclusions and tour.exclusions:
                continue  # don't clobber values already refined by hand
            db.upsert_tour(
                conn,
                Tour(
                    id=tour.id, name=tour.name, area=tour.area, category=tour.category,
                    default_stopover_count=tour.default_stopover_count,
                    meeting_point_en=tour.meeting_point_en or meeting_point_text,
                    meeting_point_jp=tour.meeting_point_jp,
                    inclusions=tour.inclusions or inclusions,
                    exclusions=tour.exclusions or exclusions,
                ),
            )
            if meeting_point_text:
                matched_meeting_points[_meeting_point_name(meeting_point_text)] = meeting_point_text

    existing_meeting_points = {mp.name for mp in db.list_meeting_points(conn)}
    for name, en_text in matched_meeting_points.items():
        if name and name not in existing_meeting_points:
            db.upsert_meeting_point(conn, MeetingPoint(id=None, name=name, en_text=en_text))
            existing_meeting_points.add(name)


def main() -> None:
    conn = db.connect()
    seed_all(conn)
    print(
        f"Seeded: {len(db.list_guides(conn))} guides, "
        f"{len(db.list_agents(conn))} agents, "
        f"{len(db.list_tours(conn))} tours, "
        f"{len(db.list_stopovers(conn))} stopovers, "
        f"{len(db.list_meeting_points(conn))} meeting points."
    )


if __name__ == "__main__":
    main()
