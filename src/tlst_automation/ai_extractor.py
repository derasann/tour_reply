"""AI-based extraction: replaces the manual "paste email into NotebookLM with
a fixed prompt" step. Calls the Claude API with the same 3 rules that used
to live in the NotebookLM prompt (see プロンプト.rtf) and returns a
BookingRequest, ready for pricing + document generation.

Unlike extractor.py (regex-based, InsideJapan-only), this handles varied
agent email formats because it's driven by an LLM rather than fixed labels.
"""

from __future__ import annotations

import json
import os

from .models import BookingRequest, Participant
from .pricing import PricingError, price_booking
from .rules import apply_bar_hop_rule, tba, tbd

DEFAULT_MODEL = os.environ.get("TLST_EXTRACTION_MODEL", "claude-sonnet-4-6")

SYSTEM_PROMPT = """あなたは旅行会社インアウトバウンド東北の予約事務アシスタントです。
旅行会社・OTAとのメールのやり取り（本文そのまま、複数通が混在している場合あり）から、
ツアー予約に必要な情報を抽出してください。以下の抽出ルールを厳守してください。

1. 未確定・不明な情報は絶対に空欄にしないこと。ガイド名や電話番号など本文に記載がない
   場合は "TBA" または "TBD" を該当フィールドに入れること（該当フィールドが無ければ
   notes に記載）。ただし tour_name / tour_date / pax は本文から読み取れる限り正確に。
2. 食事制限・アレルギーの記載があれば、原文の内容を落とさずに dietary_en
   （英語で正確に）と dietary_jp_note（ガイド向けにわかりやすい日本語）の両方に
   書き出すこと。無ければ空文字列でよい。
3. 日付は必ず ISO 8601（YYYY-MM-DD）形式の tour_date に変換すること。
4. participants は本文にある氏名（年齢が括弧書きであれば age に分離）を全て拾うこと。
5. agent（依頼元会社名）はそのまま使うこと。ref_no（予約番号/参照番号）は
   "Ref#:" や "Tour ID:" などのラベル文字列は含めず、番号・コード部分だけを
   抜き出すこと（例："InsideJapan Tours Ref#: 0000001" なら "0000001" のみ）。
6. 複数通のメールが渡され、内容が矛盾する場合（例：食事制限の対象者が後から訂正された、
   人数や日程が変更された等）は、各メール本文中の日時表記から見て最も新しいものを
   正しい情報として採用すること。どちらが新しいか判断できない場合は、本文の並び順で
   後ろにあるものを新しいとみなすこと。訂正があった場合は、その経緯（何が・いつ・
   どう変わったか）を notes に簡潔に残すこと。
7. agent_contact は依頼元担当者の「名前と電話番号」だけにすること。メールアドレスは
   含めない。「緊急連絡先」「当日のみ使用可」などのラベルや説明文も付けないこと。
   それらの背景情報は notes に書くこと。
8. メール本文中に、依頼元へ返信済みの確定請求額・計算式が明記されている場合
   （例："Total amount to be invoiced after the tour: (20,000 × 2 + private10,000)
   × 1.1 = 55,000 yen (tax included)"）は、それを stated_amount（税込最終合計、
   数字のみ）と stated_amount_formula（その計算式・金額表記をそのまま書き写したもの）
   として正確に抜き出すこと。タリフ表による自動計算より、メールに明記された確定額を
   優先するため。本文に金額が明記されていなければ両方とも空にすること（自動計算に任せる）。

抽出結果は必ず extract_booking ツールを呼び出して返してください。文章での説明は不要です。
"""

EXTRACTION_TOOL = {
    "name": "extract_booking",
    "description": "Structured booking data extracted from the email thread.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tour_name": {"type": "string"},
            "tour_date": {"type": "string", "description": "ISO 8601 YYYY-MM-DD"},
            "start_time": {"type": "string"},
            "end_time": {"type": "string"},
            "pax": {"type": "integer"},
            "participants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": ["integer", "null"]},
                    },
                    "required": ["name"],
                },
            },
            "agent": {"type": "string"},
            "agent_type": {"type": "string", "enum": ["AGT", "EXO", "BtoC"]},
            "agent_contact": {
                "type": "string",
                "description": (
                    "依頼元担当者の名前と電話番号のみ（例：'Misato Ueki / 052-456-0041'）。"
                    "メールアドレスは含めない。「緊急連絡先」等のラベル文言や説明文も付けず、"
                    "名前と電話番号だけを書くこと。"
                ),
            },
            "ref_no": {"type": "string", "description": "Number/code only, without labels like 'Ref#:' or 'Tour ID:'"},
            "tour_type": {"type": "string", "enum": ["G", "PV"]},
            "dietary_en": {"type": "string", "description": "Precise English wording, empty if none mentioned"},
            "dietary_jp_note": {"type": "string", "description": "Plain Japanese warning for the guide, empty if none mentioned"},
            "medical": {"type": "string"},
            "inquiry_date": {"type": "string", "description": "ISO 8601 date the inquiry was received, if stated"},
            "notes": {"type": "string", "description": "Anything else worth keeping for 備考・ゲスト情報・引継ぎ"},
            "stated_amount": {
                "type": ["integer", "null"],
                "description": (
                    "メール本文に確定請求額が明記されていれば、税込みの最終合計金額のみを"
                    "数字で抜き出す（例：'...= 55,000 yen (tax included)' なら 55000）。"
                    "明記されていなければ null。"
                ),
            },
            "stated_amount_formula": {
                "type": "string",
                "description": (
                    "stated_amount の根拠になった、メール本文中の計算式・金額表記をそのまま"
                    "書き写したもの。stated_amount が null の場合は空文字列。"
                ),
            },
        },
        "required": ["tour_name", "tour_date", "pax"],
    },
}


class ExtractionError(RuntimeError):
    pass


def extract_booking_request(email_text: str, *, model: str = DEFAULT_MODEL) -> BookingRequest:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("anthropic package is not installed") from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ExtractionError(
            "ANTHROPIC_API_KEY is not set. Set it as an environment variable "
            "or in .streamlit/secrets.toml before running extraction."
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extract_booking"},
        messages=[{"role": "user", "content": email_text}],
    )

    tool_use_block = next(
        (block for block in response.content if block.type == "tool_use"), None
    )
    if tool_use_block is None:
        raise ExtractionError("Claude did not return a tool_use block")

    return _to_booking(tool_use_block.input)


def _to_booking(data: dict[str, object]) -> BookingRequest:
    participants = [
        Participant(name=p["name"], age=p.get("age"))
        for p in data.get("participants", [])
    ]
    pax = data.get("pax") or len(participants) or 1

    dietary_en = str(data.get("dietary_en", "") or "")
    dietary_jp_note = str(data.get("dietary_jp_note", "") or "")
    # `dietary` keeps the English wording (used by extractor.py / reply.py
    # consumers); the Japanese guide-facing note travels in `notes` until a
    # dedicated column is worth adding.
    notes_parts = [str(data.get("notes", "") or "")]
    if dietary_jp_note:
        notes_parts.append(f"【アレルギー・食事制限（ガイド向け）】{dietary_jp_note}")
    notes = "\n".join(part for part in notes_parts if part)

    booking = BookingRequest(
        tour_date=str(data.get("tour_date", "")),
        tour_name=str(data.get("tour_name", "")),
        pax=int(pax),
        participants=participants,
        agent=str(data.get("agent", "") or ""),
        agent_type=str(data.get("agent_type", "AGT") or "AGT"),
        agent_contact=str(data.get("agent_contact", "") or ""),
        ref_no=str(data.get("ref_no", "") or ""),
        tour_type=str(data.get("tour_type", "G") or "G"),
        dietary=dietary_en,
        medical=str(data.get("medical", "") or ""),
        notes=notes,
        start_time=str(data.get("start_time", "") or ""),
        end_time=str(data.get("end_time", "") or ""),
        inquiry_date=str(data.get("inquiry_date", "") or ""),
        guide_name=tba(None),
        guide_mobile=tbd(None),
        emergency_contact=tbd(None),
    )

    # Prefer whatever confirmed amount the agent thread itself already
    # states (rule 8) over the tariff-table formula: it already accounts
    # for ad hoc surcharges (e.g. "+private10,000"), minimum-charge
    # policies, and tour-name variants the tariff table's exact-match
    # lookup can't -- pricing.py's formula is only a fallback for when the
    # email doesn't state a final amount. Either way, this is the customer
    # invoice amount; the bar-hop food/drink budget below is a separate,
    # guide-side figure and must never overwrite it (see rules.py).
    stated_amount = data.get("stated_amount")
    stated_amount_formula = str(data.get("stated_amount_formula", "") or "")
    if stated_amount is not None:
        booking = _with(
            booking,
            amount=int(stated_amount),
            amount_formula=stated_amount_formula or f"{int(stated_amount):,}円（メール記載）",
        )
    else:
        try:
            booking = price_booking(booking)
        except PricingError:
            # Unknown tour in the pricing table -- leave amount as TBD rather
            # than raising, per rule 3 ("未確定の情報...TBAまたはTBD").
            booking = _with(booking, amount=None, amount_formula=tbd(None))

    bar_hop_info = apply_bar_hop_rule(booking.tour_name, booking.tour_date, booking.pax)
    if bar_hop_info:
        bar_hop_note = (
            f"【バーホッピング判定】{bar_hop_info['shop_count']}軒案内"
            f"（{'金土日祝日' if bar_hop_info['shop_count'] == 2 else '平日'}実施）。"
            f"飲食代目安: {bar_hop_info['food_budget_formula']}"
        )
        if bar_hop_info["guide_fee_addon"]:
            bar_hop_note += f"（3軒目の店舗手配分としてガイド謝金に+{bar_hop_info['guide_fee_addon']:,}円を加算してください）"
        notes = f"{booking.notes}\n{bar_hop_note}".strip()
        if bar_hop_info["congestion_notice_en"]:
            notes = f"{notes}\n{bar_hop_info['congestion_notice_en']}".strip()
        booking = _with(booking, notes=notes)

    return booking


def _with(booking: BookingRequest, **changes: object) -> BookingRequest:
    from dataclasses import replace

    return replace(booking, **changes)


GUIDE_REQUEST_SYSTEM_PROMPT = """あなたは旅行会社のガイド依頼書（ガイドへの行程指示書）を読み取るアシスタントです。
渡されたガイド依頼書のテキストから、ツアー名と行程表（時間・立ち寄り先・支払額・支払方法・
立ち寄り先情報）を抽出してください。

- 行程表の各行を順番どおりに全て拾うこと（集合・タクシー移動・解散なども1行として含める）。
- unit_price は、その立ち寄り先で1人あるいは1台あたりの支払額が明確な単一の数値として
  読み取れる場合のみ円単位の整数で入れること（例："@200円 × 1" なら 200、
  "@570円 + @410円 + ガイド分" のように複数の金額が混在し単一の単価に定まらない場合は null）。
- 抽出結果は必ず extract_guide_request ツールを呼び出して返すこと。文章での説明は不要。
"""

GUIDE_REQUEST_EXTRACTION_TOOL = {
    "name": "extract_guide_request",
    "description": "Structured itinerary data extracted from a guide-request document (ガイド依頼書).",
    "input_schema": {
        "type": "object",
        "properties": {
            "tour_name": {"type": "string"},
            "itinerary": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "time_label": {"type": "string"},
                        "stopover_name": {"type": "string"},
                        "payment_label": {"type": "string"},
                        "payment_method": {"type": "string"},
                        "stopover_info": {
                            "type": "string",
                            "description": "Address/phone of the stopover, if stated",
                        },
                        "unit_price": {
                            "type": ["integer", "null"],
                            "description": "Single clear per-item/per-person/per-vehicle price in yen, else null",
                        },
                    },
                    "required": ["time_label", "stopover_name"],
                },
            },
        },
        "required": ["tour_name", "itinerary"],
    },
}


def _call_extraction_tool(
    system_prompt: str, tool: dict, text: str, *, model: str = DEFAULT_MODEL
) -> dict[str, object]:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("anthropic package is not installed") from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ExtractionError(
            "ANTHROPIC_API_KEY is not set. Set it as an environment variable "
            "or in .streamlit/secrets.toml before running extraction."
        )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=4000,
        system=system_prompt,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": text}],
    )

    tool_use_block = next(
        (block for block in response.content if block.type == "tool_use"), None
    )
    if tool_use_block is None:
        raise ExtractionError("Claude did not return a tool_use block")

    return tool_use_block.input


def extract_guide_request_document(text: str, *, model: str = DEFAULT_MODEL) -> dict[str, object]:
    """Parse a past ガイド依頼書 (guide request doc) into tour_name +
    itinerary rows, for saving as a reusable itinerary variant / seeding
    the stopover price master. Returns the raw tool_use input (dict with
    "tour_name" and "itinerary" list of dicts including "unit_price").
    """
    return _call_extraction_tool(GUIDE_REQUEST_SYSTEM_PROMPT, GUIDE_REQUEST_EXTRACTION_TOOL, text, model=model)


CONFIRMATION_SYSTEM_PROMPT = """あなたは旅行会社のBooking Confirmation（依頼元・ガイド向けの英語の確認書）を
読み取るアシスタントです。渡されたテキストから、ツアー名・集合場所（英語・日本語）・
Inclusions（含まれるもの）・Exclusions（含まれないもの）を抽出してください。

- 集合場所は英語表記(meeting_point_en)と日本語表記(meeting_point_jp)を分けて抜き出すこと。
  どちらか一方しか無ければ、あるほうだけ入れて他方は空文字列でよい。
- Inclusions/Exclusionsは書類にある箇条書きを1項目ずつ配列に分けること。
- 抽出結果は必ず extract_confirmation ツールを呼び出して返すこと。文章での説明は不要。
"""

CONFIRMATION_EXTRACTION_TOOL = {
    "name": "extract_confirmation",
    "description": "Structured meeting-point/inclusions/exclusions data from a Booking Confirmation document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tour_name": {"type": "string"},
            "meeting_point_en": {"type": "string"},
            "meeting_point_jp": {"type": "string"},
            "inclusions": {"type": "array", "items": {"type": "string"}},
            "exclusions": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["tour_name"],
    },
}


def extract_confirmation_document(text: str, *, model: str = DEFAULT_MODEL) -> dict[str, object]:
    """Parse a past Booking Confirmation into tour_name + meeting point
    (EN/JP) + inclusions/exclusions, for seeding the Meeting Point master
    and cross-checking the Tour master's tariff-derived wording.
    """
    return _call_extraction_tool(CONFIRMATION_SYSTEM_PROMPT, CONFIRMATION_EXTRACTION_TOOL, text, model=model)
