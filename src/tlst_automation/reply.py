from __future__ import annotations

from .models import BookingRequest

SIGNATURE = """─────────────────────────────────────────────
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
─────────────────────────────────────────────"""


def render_reply(booking: BookingRequest, contact_name: str = "Partner") -> str:
    if booking.language.upper() == "JP":
        return render_japanese_reply(booking, contact_name)
    return render_english_reply(booking, contact_name)


def render_english_reply(booking: BookingRequest, contact_name: str = "Partner") -> str:
    participants = ", ".join(
        f"{participant.name} ({participant.age})" if participant.age else participant.name
        for participant in booking.participants
    )
    dietary = booking.dietary or "None"
    medical = f"Medical note: {booking.medical}\n" if booking.medical else ""

    return f"""Dear {contact_name}-san,

Thank you very much for your continued support and for your new booking request.
We are pleased to confirm the reservation for {booking.agent} Ref#: {booking.ref_no} as follows:

Tour: {booking.tour_name}
Date: {booking.tour_date}
Time: {booking.start_time} - {booking.end_time}
Participants: {participants}
Dietary requirements: {dietary}
{medical}
Total amount to be invoiced after the tour:
{booking.amount_formula} yen (tax included)

We will send a PDF confirmation approximately one month before the tour,
including the guide's name and meeting point details.

Thank you very much for your cooperation.
We look forward to welcoming your clients to Sendai.

Kind regards,
Kyoko Onodera

{SIGNATURE}"""


def render_japanese_reply(booking: BookingRequest, contact_name: str = "ご担当者") -> str:
    participants = "、".join(
        f"{participant.name}（{participant.age}）" if participant.age else participant.name
        for participant in booking.participants
    )
    dietary = booking.dietary or "なし"

    return f"""{contact_name}様

いつもお世話になっております。

以下の内容でお受けいたします。

ツアー名：{booking.tour_name}
ご利用日：{booking.tour_date}
開始時間：{booking.start_time}
ご参加者：{participants}
食事制限：{dietary}

ツアー終了後の請求予定金額：
{booking.amount_formula}円（税込）

ツアー実施の約1か月前に、ガイド名を含む最終確認書（PDF）をお送りいたします。

何卒よろしくお願いいたします。

小野寺恭子
株式会社インアウトバウンド東北

{SIGNATURE}"""
