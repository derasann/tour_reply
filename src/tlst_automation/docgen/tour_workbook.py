"""Fills templates/tour_workbook_template.xlsx (the real 0625Hungry.xlsx)
with a booking's data:
  - 予約情報 sheet -> the internal 社内共有シート (management sheet)
  - 予約確認書(Oyster) sheet -> the Booking Confirmation

Name/Guests/Tour/Date on the Confirmation sheet are formulas in the
original template (='予約情報'!I10 etc). We overwrite them with literal
values instead of leaving the cross-sheet reference, because LibreOffice's
headless PDF export has a bug where hiding 予約情報 (to export the
Confirmation sheet alone) still renders it as an extra page whenever a
visible sheet's formula references it. See docgen/pdf_export.py.

See docgen/xlsx_lowlevel.py for why this edits XML directly instead of
going through openpyxl.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from ..models import BookingRequest
from ..rules import format_dietary_for_confirmation, tba, tbd
from . import xlsx_lowlevel as xl

TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "tour_workbook_template.xlsx"

SHEET1 = "xl/worksheets/sheet1.xml"  # 予約情報
SHEET2 = "xl/worksheets/sheet2.xml"  # 予約確認書(Oyster)
DRAWING2 = "xl/drawings/drawing2.xml"  # Dietary / Inclusions & Exclusions box

CHECKLIST_CELL_BY_LABEL = {
    "見積提出": "C18",
    "コンファメーション送付": "C19",
    "インボイス送付": "C20",
    "ガイド手配": "P18",
    "保険加入": "P21",
    "ガイド報告": "AC18",
    "ガイド清算シート記入確認": "AC19",
}

EXTRA_SLOTS = {
    "pre": [("C21", "D21"), ("C22", "D22"), ("C23", "D23")],
    "during": [("P19", "Q19"), ("P20", "Q20"), ("P22", "Q22"), ("P23", "Q23")],
    "post": [("AC20", "AD20"), ("AC21", "AD21"), ("AC22", "AD22"), ("AC23", "AD23")],
}

CHECKED_GLYPH = "☑"  # ☑


def _participants_text(booking: BookingRequest) -> str:
    return ", ".join(
        f"{p.name} ({p.age})" if p.age is not None else p.name for p in booking.participants
    )


def _display_date(iso_date: str) -> str:
    try:
        parsed = date.fromisoformat(iso_date)
    except ValueError:
        return iso_date
    return parsed.strftime("%A %d %B %Y")


def _feedback_text(booking: BookingRequest) -> str:
    fb = booking.feedback
    if fb is None:
        return ""
    lines = [
        f"ゲスト出身国籍（エリア）: {fb.guest_country_area or tba(None)}",
        f"ゲスト出身国名: {fb.guest_country_name or tba(None)}",
        f"お客様情報（属性）: {fb.guest_attribute or tba(None)}",
        f"お客様情報（人数）: {fb.guest_pax if fb.guest_pax is not None else tbd(None)}",
        f"本ツアー前の日本旅行の行程: {fb.pre_itinerary or tba(None)}",
        f"本ツアー後の日本旅行の行程: {fb.post_itinerary or tba(None)}",
        f"日本は何回目？ 不明は0にチェック: {fb.visit_count if fb.visit_count is not None else 0}",
        f"日本旅行の全体日数: {fb.stay_duration or tba(None)}",
        f"東北への滞在を選んだ理由: {fb.stay_reason or tba(None)}",
        f"お客様が何にご興味を持たれていたか・ツアー中のご様子など: {fb.interests or tba(None)}",
        "",
        "もしご連絡事項がありましたらこちらの欄をご利用ください。個別にご連絡を入れていただいても構いません。:",
        fb.notes,
    ]
    return "\n".join(lines)


def _apply_checklist(xml: str, items) -> str:
    used_labels = set()
    extras: list = []
    for item in items:
        cell = CHECKLIST_CELL_BY_LABEL.get(item.label)
        if cell:
            used_labels.add(item.label)
            if item.done:
                xml = xl.set_inline_string(xml, cell, CHECKED_GLYPH)
        else:
            extras.append(item)
    return xml, extras


def _fill_extra_slots(xml: str, extras, slots) -> str:
    for (checkbox_cell, label_cell), item in zip(slots, extras):
        xml = xl.set_inline_string(xml, label_cell, item.label)
        if item.done:
            xml = xl.set_inline_string(xml, checkbox_cell, CHECKED_GLYPH)
    return xml


def _fill_sheet1(xml: str, booking: BookingRequest) -> str:
    xml = xl.set_inline_string(xml, "D2", booking.booking_no or tba(None))
    xml = xl.set_inline_string(xml, "H2", booking.tour_name)
    xml = xl.set_inline_string(xml, "AE2", booking.status or "予約受付")
    xml = xl.set_inline_string(xml, "AK2", booking.payment_status or "入金待ち")
    xml = xl.set_inline_string(xml, "AC8", booking.assignee_1st or tba(None))
    if booking.assignee_2nd:
        xml = xl.set_inline_string(xml, "AC9", booking.assignee_2nd)
    xml = xl.set_inline_string(xml, "AK9", booking.guide_name)
    if booking.inquiry_date:
        try:
            xml = xl.set_number(xml, "AK8", xl.excel_date_serial(date.fromisoformat(booking.inquiry_date)))
        except ValueError:
            xml = xl.set_inline_string(xml, "AK8", booking.inquiry_date)
    xml = xl.set_inline_string(xml, "I10", _participants_text(booking) or tba(None))
    xml = xl.set_number(xml, "I11", booking.pax)
    xml = xl.set_inline_string(xml, "AC10", _display_date(booking.tour_date))
    xml = xl.set_inline_string(xml, "AC11", booking.agent or tba(None))
    xml = xl.set_inline_string(xml, "AK11", booking.agent_contact or tba(None))

    xml = xl.set_inline_string(xml, "I12", booking.notes or tba(None))

    xml, pre_extra = _apply_checklist(xml, booking.checklist_pre)
    xml, during_extra = _apply_checklist(xml, booking.checklist_during)
    xml, post_extra = _apply_checklist(xml, booking.checklist_post)
    xml = _fill_extra_slots(xml, pre_extra, EXTRA_SLOTS["pre"])
    xml = _fill_extra_slots(xml, during_extra, EXTRA_SLOTS["during"])
    xml = _fill_extra_slots(xml, post_extra, EXTRA_SLOTS["post"])

    if booking.guide_fee is not None:
        xml = xl.set_number(xml, "O29", booking.guide_fee)
    else:
        xml = xl.clear_cell(xml, "O29")
    if booking.insurance_amount is not None:
        xml = xl.set_number(xml, "O35", booking.insurance_amount)
    else:
        xml = xl.clear_cell(xml, "O35")

    extra_rows = ["C30", "C31", "C32", "C33", "C34"]
    extra_amount_cols = ["O30", "O31", "O32", "O33", "O34"]
    for (label_cell, amount_cell), line in zip(zip(extra_rows, extra_amount_cols), booking.sales_lines):
        xml = xl.set_inline_string(xml, label_cell, line.label)
        if line.amount is not None:
            xml = xl.set_number(xml, amount_cell, line.amount)

    if booking.amount is not None:
        xml = xl.set_number(xml, "T29", booking.amount)

    if booking.feedback is not None:
        xml = xl.set_inline_string(xml, "C43", _feedback_text(booking))

    return xml


def _fill_sheet2(xml: str, booking: BookingRequest) -> str:
    # E4/E5/E13/E14 are formulas in the template (='予約情報'!I10 etc). We
    # overwrite them with the same literal values instead of leaving the
    # cross-sheet reference: LibreOffice's headless PDF export has a bug
    # where hiding 予約情報 (to export Booking Confirmation alone) still
    # renders it as an extra page whenever a visible sheet's formula
    # references it. Writing literal values here removes that dependency.
    xml = xl.set_inline_string(xml, "E4", _participants_text(booking) or tba(None))
    xml = xl.set_number(xml, "E5", booking.pax)
    xml = xl.set_inline_string(xml, "E13", booking.tour_name)
    xml = xl.set_inline_string(xml, "E14", _display_date(booking.tour_date))

    if booking.start_time:
        hour, _, minute = booking.start_time.partition(":")
        try:
            xml = xl.set_number(xml, "E15", xl.excel_time_fraction(int(hour), int(minute or 0)))
        except ValueError:
            pass
    if booking.end_time:
        hour, _, minute = booking.end_time.partition(":")
        try:
            xml = xl.set_number(xml, "G15", xl.excel_time_fraction(int(hour), int(minute or 0)))
        except ValueError:
            pass

    xml = xl.set_inline_string(xml, "E16", booking.guide_name)
    xml = xl.set_inline_string(
        xml, "F16", f"Emargency Contact:{booking.emergency_contact}  (Mobile/WhatsAPP)"
    )
    xml = xl.set_inline_string(xml, "E17", booking.guide_mobile)
    xml = xl.set_inline_string(xml, "E18", booking.meeting_point_en or tba(None))
    xml = xl.set_inline_string(xml, "F18", booking.meeting_point_jp or tba(None))
    return xml


def _fill_drawing2(xml: str, booking: BookingRequest) -> str:
    dietary = format_dietary_for_confirmation(booking.dietary)
    xml = xl.replace_drawing_text_run(xml, 1, dietary)

    inclusion_lines = booking.inclusions[:5]
    for offset, text in enumerate(inclusion_lines):
        xml = xl.replace_drawing_text_run(xml, 5 + offset, text)

    if booking.exclusions:
        xml = xl.replace_drawing_text_run(xml, 12, booking.exclusions[0])

    return xml


def generate_tour_workbook(booking: BookingRequest, output_path: Path) -> Path:
    """Copy the real xlsx master and fill it in for one booking.

    Fills both 予約情報 (internal sheet) and 予約確認書(Oyster) (Booking
    Confirmation, via formulas back to 予約情報 plus its own guide/meeting
    point/dietary fields).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEMPLATE_PATH, output_path)

    parts = xl.load_zip_parts(output_path)
    sheet1 = parts[SHEET1].decode("utf-8")
    sheet2 = parts[SHEET2].decode("utf-8")
    drawing2 = parts[DRAWING2].decode("utf-8")

    sheet1 = _fill_sheet1(sheet1, booking)
    sheet2 = _fill_sheet2(sheet2, booking)
    drawing2 = _fill_drawing2(drawing2, booking)

    parts[SHEET1] = sheet1.encode("utf-8")
    parts[SHEET2] = sheet2.encode("utf-8")
    parts[DRAWING2] = drawing2.encode("utf-8")

    xl.write_zip_parts(output_path, parts)
    return output_path
