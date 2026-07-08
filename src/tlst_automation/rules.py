"""Business rules ported from プロンプト.rtf (the NotebookLM extraction prompt).

1. Bar-hopping tours: Fri/Sat/Sun/public-holiday -> 2-shop plan. Weekdays ->
   3-shop plan. Confirmed against real guide-request examples
   (#1263106_0714_barhopping.pdf, a Tuesday/weekday 3-shop tour): the
   food & drink budget formula (3,000円×2軒×人数 + guide drink 750円×2軒)
   always uses the fixed "2軒" baseline regardless of the actual shop
   count -- e.g. pax=1 -> 7,500円, pax=2 -> 13,500円, matching
   6,000×pax+1,500 exactly. The 3rd (weekday-only) shop is instead paid for
   via a flat +1,000円 addition to the guide's own fee (visible in that
   same example as "ガイド謝金 6,000円: 店舗予約+1,000円含む"), not by
   scaling the food budget. This is the guide-side cost/itinerary budget,
   separate from the customer invoice amount (see pricing.py).
2. Dietary/allergy info: precise English wording for the Booking
   Confirmation, bolded plain-Japanese wording for the guide request.
3. Unknown guide name/phone/fee etc. must never be left blank - use
   "TBA" or "TBD".
"""

from __future__ import annotations

import re
from datetime import date, datetime

import jpholiday

from .models import TBA, TBD

BAR_HOP_KEYWORDS = ("bar hop", "izakaya", "yokocho", "snack bar")


def normalize_tour_name(name: str) -> str:
    """Loose key for matching tour names across sources (tariff PDF, AI
    extraction from emails/guide-requests, hand-typed master data) that
    don't always agree character-for-character (spacing, dashes, curly vs
    straight quotes, parenthetical notes)."""
    name = name.lower()
    name = re.sub(r"[’'“”\"]", "", name)
    name = re.sub(r"[\-–—]", " ", name)
    name = re.sub(r"[()（）]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def tour_names_match(a: str, b: str) -> bool:
    """True if two tour names likely refer to the same tour, tolerating the
    spelling/formatting drift described in normalize_tour_name() plus a
    single inserted/dropped/glued word (e.g. AI extraction from a guide
    request adding "izakaya" that a booking email's extraction omits).

    Two checks, either is enough:
    - normalized character substring (catches glued-prefix PDF text
      artifacts like "BaNightlife..." containing "Nightlife...")
    - word-set symmetric difference of at most 1 (catches a whole extra
      word inserted anywhere, which breaks substring matching)
    Requires at least 8 normalized characters / 2 words so short generic
    names don't false-positive against each other, and caps the word-set
    check at a 1-word difference so genuinely different tours that merely
    share most of their name (e.g. two different "...Hopping in Sendai"
    tours) aren't merged.
    """
    norm_a, norm_b = normalize_tour_name(a), normalize_tour_name(b)
    if not norm_a or not norm_b:
        return False
    if len(norm_a) >= 8 and len(norm_b) >= 8 and (norm_a in norm_b or norm_b in norm_a):
        return True
    tokens_a, tokens_b = set(norm_a.split()), set(norm_b.split())
    if len(tokens_a) < 2 or len(tokens_b) < 2:
        return False
    return len(tokens_a ^ tokens_b) <= 1

GUIDE_DRINK_PRICE = 750
PER_SHOP_FOOD_PRICE = 3000
FOOD_BUDGET_SHOP_BASELINE = 2  # always used in the formula, even for 3-shop weekday tours
WEEKDAY_SHOP_COUNT = 3
WEEKEND_HOLIDAY_SHOP_COUNT = 2
WEEKDAY_EXTRA_SHOP_GUIDE_FEE = 1000  # extra shop-booking fee paid to the guide, not the food budget

CONGESTION_NOTICE_EN = (
    "On Fridays, Saturdays, Sundays and Public Holidays, izakaya tend to be "
    "very crowded, so you will visit two instead of three during the tour. "
    "You will still enjoy a total of 3 drinks and the volume/quality of "
    "food will be the same."
)  # verbatim from the official tariff (Tariff_2025_TLST.pdf)


def is_bar_hopping_tour(tour_name: str) -> bool:
    lowered = tour_name.lower()
    return any(keyword in lowered for keyword in BAR_HOP_KEYWORDS)


def is_weekend_or_holiday(tour_date: str) -> bool:
    """tour_date must be an ISO date string (YYYY-MM-DD)."""
    parsed = _parse_iso_date(tour_date)
    if parsed is None:
        return False
    is_weekend = parsed.weekday() in (4, 5, 6)  # Fri, Sat, Sun
    return is_weekend or jpholiday.is_holiday(parsed)


def bar_hop_shop_count(tour_date: str) -> int:
    return (
        WEEKEND_HOLIDAY_SHOP_COUNT
        if is_weekend_or_holiday(tour_date)
        else WEEKDAY_SHOP_COUNT
    )


def bar_hop_food_budget(pax: int) -> tuple[int, str]:
    """Guest food & drink budget. Always uses the fixed 2-shop baseline,
    regardless of whether the itinerary actually has 2 or 3 shops."""
    food_cost = PER_SHOP_FOOD_PRICE * FOOD_BUDGET_SHOP_BASELINE * pax
    guide_drink_cost = GUIDE_DRINK_PRICE * FOOD_BUDGET_SHOP_BASELINE
    total = food_cost + guide_drink_cost
    formula = (
        f"{PER_SHOP_FOOD_PRICE:,}円 × {FOOD_BUDGET_SHOP_BASELINE}軒 × {pax}名 "
        f"+ ガイドドリンク{GUIDE_DRINK_PRICE:,}円 × {FOOD_BUDGET_SHOP_BASELINE}軒 = {total:,}円"
    )
    return total, formula


def bar_hop_guide_fee_addon(shop_count: int) -> int:
    """Extra flat fee paid to the guide for booking the 3rd (weekday-only) shop."""
    return WEEKDAY_EXTRA_SHOP_GUIDE_FEE if shop_count == WEEKDAY_SHOP_COUNT else 0


def apply_bar_hop_rule(tour_name: str, tour_date: str, pax: int) -> dict[str, object] | None:
    """Return shop-count/food-budget/guide-fee-addon/notice info for the
    guide request, or None if this isn't a bar-hop tour. Does not affect
    the customer invoice amount -- that always comes from pricing.py.
    """
    if not is_bar_hopping_tour(tour_name):
        return None
    shop_count = bar_hop_shop_count(tour_date)
    food_budget_amount, food_budget_formula = bar_hop_food_budget(pax)
    return {
        "shop_count": shop_count,
        "food_budget_amount": food_budget_amount,
        "food_budget_formula": food_budget_formula,
        "guide_fee_addon": bar_hop_guide_fee_addon(shop_count),
        "congestion_notice_en": (
            CONGESTION_NOTICE_EN if shop_count == WEEKEND_HOLIDAY_SHOP_COUNT else ""
        ),
    }


GUIDE_FEE_HOURLY_RATE = 2000
BAR_HOP_BASE_GUIDE_FEE = 5000
SHOP_ARRANGEMENT_BONUS = 1000
GUEST_COUNT_FEE_STEP = 1000  # per guest beyond 2


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    try:
        hour_str, minute_str = value.strip().split(":")
        return int(hour_str), int(minute_str)
    except (ValueError, AttributeError):
        return None


def tour_duration_hours(start_time: str, end_time: str) -> float | None:
    start = _parse_hhmm(start_time)
    end = _parse_hhmm(end_time)
    if start is None or end is None:
        return None
    minutes = (end[0] * 60 + end[1]) - (start[0] * 60 + start[1])
    if minutes <= 0:
        return None
    return minutes / 60


def guest_count_fee_addon(pax: int) -> int:
    return max(0, pax - 2) * GUEST_COUNT_FEE_STEP


def compute_guide_base_fee(
    tour_name: str,
    pax: int,
    start_time: str,
    end_time: str,
    *,
    shop_arrangement_bonus: bool = False,
    duration_hours_override: float | None = None,
) -> tuple[int | None, str]:
    """Guide base-fee formula for Miyagi-departure tours (Aomori/Yamagata
    etc. tours are run by the local team and negotiated case-by-case, so
    this formula doesn't apply to them).

    Bar-hopping (Iroha Yokocho etc.): flat 5,000円, +1,000円 if the guide
    personally handles the shop reservations. Everything else: tour
    duration (hours) × 2,000円, plus 1,000円 per guest beyond 2 (i.e. pax 3
    -> +1,000, pax 4 -> +2,000, ...).

    `duration_hours_override`, when given, is used instead of the raw
    start_time/end_time difference -- this is the tour's own standard
    duration from the Tour master, so that extra time in a booking's actual
    times (e.g. a hotel pickup added on) doesn't inflate this base formula;
    see extra_duration_fee() for billing that difference separately.
    """
    if is_bar_hopping_tour(tour_name):
        amount = BAR_HOP_BASE_GUIDE_FEE
        formula = f"バーホッピング基本謝金 {BAR_HOP_BASE_GUIDE_FEE:,}円"
        if shop_arrangement_bonus:
            amount += SHOP_ARRANGEMENT_BONUS
            formula += f" + 店舗調整担当 {SHOP_ARRANGEMENT_BONUS:,}円"
        return amount, formula

    duration = duration_hours_override if duration_hours_override is not None else tour_duration_hours(start_time, end_time)
    if duration is None:
        return None, "開始・終了時間が不明なため自動計算できません"
    amount = round(duration * GUIDE_FEE_HOURLY_RATE)
    formula = f"{duration:g}時間 × {GUIDE_FEE_HOURLY_RATE:,}円 = {amount:,}円"
    addon = guest_count_fee_addon(pax)
    if addon:
        amount += addon
        formula += f" + 人数加算（{pax}名）{addon:,}円"
    return amount, formula


def extra_duration_fee(
    start_time: str, end_time: str, standard_duration_hours: float | None
) -> tuple[int, str]:
    """Extra guide-fee for actual time beyond a tour's standard duration
    (e.g. an added hotel pickup/drop-off leg), meant to be billed via
    BookingRequest.guide_fee_adjustment instead of folded into the base-fee
    formula above. Returns (0, "") if there's no standard duration to
    compare against, or the actual time isn't longer.
    """
    if standard_duration_hours is None:
        return 0, ""
    actual_duration = tour_duration_hours(start_time, end_time)
    if actual_duration is None or actual_duration <= standard_duration_hours:
        return 0, ""
    extra_hours = actual_duration - standard_duration_hours
    extra_fee = round(extra_hours * GUIDE_FEE_HOURLY_RATE)
    note = (
        f"実際の時間が基準（{standard_duration_hours:g}時間）より{extra_hours:g}時間長いため、"
        f"送迎等の調整分として{extra_fee:,}円を自動反映"
    )
    return extra_fee, note


def tour_matches_any_name(tour_name: str, candidate_name: str, candidate_exo_name: str = "") -> bool:
    """Like tour_names_match, but also checks a Tour master entry's EXO-side
    alias name -- EXO correspondence often refers to the same tour with
    different wording than the AGT/BtoC name (see master.Tour.exo_name)."""
    return tour_names_match(tour_name, candidate_name) or (
        bool(candidate_exo_name) and tour_names_match(tour_name, candidate_exo_name)
    )


# Owner's own mobile is fixed on every guide request's emergency-contact
# line (see reply.py's SIGNATURE for the same number); only the messenger
# thread's guide nickname portion changes per booking. Real example:
# "070-5327-0029(小野寺）＆ 【ちえさん】 TTC個別連絡メッセンジャースレッド"
ONODERA_MOBILE = "070-5327-0029"


def format_guide_emergency_contact(guide_nickname_or_name: str) -> str:
    name = guide_nickname_or_name.strip() if guide_nickname_or_name else ""
    if not name or name == TBA:
        return tbd(None)
    return f"{ONODERA_MOBILE}(小野寺）＆【{name}さん】TTC個別連絡メッセンジャースレッド"


def format_dietary_for_confirmation(dietary_en: str) -> str:
    """Booking Confirmation must state dietary/allergy info precisely in English."""
    return dietary_en.strip() if dietary_en.strip() else "None declared"


def format_dietary_for_guide_request(dietary_jp_note: str) -> str:
    """Guide request must restate dietary/allergy info in plain, bolded Japanese."""
    return dietary_jp_note.strip() if dietary_jp_note.strip() else "特になし"


def tba(value: str | None) -> str:
    return value.strip() if value and value.strip() else TBA


def tbd(value: str | None) -> str:
    return value.strip() if value and value.strip() else TBD


def tba_number(value: int | None) -> str:
    return str(value) if value is not None else TBD


def _parse_iso_date(raw_date: str) -> date | None:
    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        pass
    for fmt in ("%A %d %B %Y", "%A, %d %B %Y", "%d %B %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw_date.strip(), fmt).date()
        except ValueError:
            continue
    return None
