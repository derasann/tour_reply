from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s()\-ー−]{7,}\d)(?!\d)")
TITLE_NAME_RE = re.compile(
    r"\b(M\s*r\s*s|M\s*r|M\s*s|Miss|Dr)\.?\s+([A-Z][A-Za-z'’-]*(?:\s+[A-Z][A-Za-z'’-]*){0,5})",
    flags=re.IGNORECASE,
)
JAPANESE_NAME_RE = re.compile(r"([一-龥ぁ-んァ-ヴー]{2,8})(様|さん|氏)")
BOOKING_NAME_RE = re.compile(
    r"((?:Booking Name|予約名Booking Name)\s+)(.*?)(?=\s*(?:BookingDepartment|予約部|BookingReference|弊社ツアー番号|$))",
    flags=re.IGNORECASE | re.DOTALL,
)
EXO_SUBJECT_NAME_RE = re.compile(
    r"((?:New Booking Request|New booking request)\s*\|\s*[^/\n]+/\s*)(.*?)(\s*/\s*\d{2}-[A-Za-z]{3})",
    flags=re.IGNORECASE | re.DOTALL,
)
REF_SURNAME_RE = re.compile(r"((?:#|Ref#?:?)\s*\d+\s+)([A-Z][A-Za-z'’-]+)(?=\s*[-/])")


def extract_pdf_text(pdf_path: str | Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


def mask_pdf(
    source_pdf: str | Path,
    output_pdf: str | Path | None = None,
    *,
    strength: int = 3,
) -> Path:
    source = Path(source_pdf)
    output = Path(output_pdf) if output_pdf else source.with_name(f"{source.stem}_masked.pdf")
    masked_text = mask_text(extract_pdf_text(source), strength=strength)
    try:
        write_text_pdf(masked_text, output)
    except PermissionError:
        output = _fallback_output_path(source)
        write_text_pdf(masked_text, output)
    return output


def mask_text(text: str, *, strength: int = 3) -> str:
    strength = max(1, min(5, int(strength)))
    text = EMAIL_RE.sub(lambda match: _mask_email(match.group(0), strength), text)
    text = PHONE_RE.sub(lambda match: _mask_phone(match.group(0), strength), text)
    text = TITLE_NAME_RE.sub(lambda match: _mask_title_name(match, strength), text)
    text = BOOKING_NAME_RE.sub(lambda match: _mask_booking_name(match, strength), text)
    text = EXO_SUBJECT_NAME_RE.sub(lambda match: _mask_subject_name(match, strength), text)
    text = REF_SURNAME_RE.sub(lambda match: match.group(1) + _mask_word(match.group(2), _visible_count(len(match.group(2)), strength)), text)
    text = JAPANESE_NAME_RE.sub(lambda match: _mask_japanese_name(match, strength), text)
    return text


def write_text_pdf(text: str, output_pdf: str | Path) -> None:
    _register_japanese_font()
    output = Path(output_pdf)
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Masked PDF",
    )
    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        "MaskedBody",
        parent=styles["BodyText"],
        fontName="HeiseiKakuGo-W5",
        fontSize=9,
        leading=13,
        wordWrap="CJK",
    )
    story = []
    for block in text.split("\n\n"):
        safe_block = _escape_xml(block).replace("\n", "<br/>")
        if safe_block.strip():
            story.append(Paragraph(safe_block, style))
            story.append(Spacer(1, 4 * mm))
    doc.build(story)


def _fallback_output_path(source: Path) -> Path:
    output_dir = Path.cwd() / "masked_outputs"
    output_dir.mkdir(exist_ok=True)
    return output_dir / f"{source.stem}_masked.pdf"


def _register_japanese_font() -> None:
    if "HeiseiKakuGo-W5" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))


def _mask_email(email: str, strength: int) -> str:
    local, _, domain = email.partition("@")
    visible_local = _visible_count(len(local), strength)
    visible_domain = 1 if strength >= 4 else 2
    domain_parts = domain.split(".")
    domain_name = domain_parts[0]
    suffix = "." + ".".join(domain_parts[1:]) if len(domain_parts) > 1 else ""
    return (
        _mask_word(local, visible_local)
        + "@"
        + _mask_word(domain_name, visible_domain)
        + suffix
    )


def _mask_phone(phone: str, strength: int) -> str:
    digits = re.sub(r"\D", "", phone)
    keep = max(1, 5 - strength)
    if len(digits) <= keep:
        return "*" * len(phone)
    masked_digits = "*" * (len(digits) - keep) + digits[-keep:]
    output = []
    index = 0
    for char in phone:
        if char.isdigit():
            output.append(masked_digits[index])
            index += 1
        else:
            output.append(char)
    return "".join(output)


def _mask_title_name(match: re.Match[str], strength: int) -> str:
    title = _normalize_title(match.group(1))
    name = match.group(2)
    masked = " ".join(_mask_word(part, _visible_count(len(part), strength)) for part in name.split())
    return f"{title}. {masked}"


def _mask_booking_name(match: re.Match[str], strength: int) -> str:
    return match.group(1) + _mask_name_phrase(match.group(2), strength)


def _mask_subject_name(match: re.Match[str], strength: int) -> str:
    return match.group(1) + _mask_name_phrase(match.group(2), strength) + match.group(3)


def _mask_japanese_name(match: re.Match[str], strength: int) -> str:
    name = match.group(1)
    suffix = match.group(2)
    visible = 1 if strength >= 3 else 2
    return _mask_word(name, min(visible, len(name))) + suffix


def _visible_count(length: int, strength: int) -> int:
    ratio = {1: 0.65, 2: 0.5, 3: 0.35, 4: 0.25, 5: 0.15}[strength]
    return max(1, min(length, round(length * ratio)))


def _mask_word(value: str, visible_count: int) -> str:
    if len(value) <= visible_count:
        return value
    return value[:visible_count] + "*" * (len(value) - visible_count)


def _mask_name_phrase(value: str, strength: int) -> str:
    return re.sub(
        r"[A-Z][A-Za-z'’-]*",
        lambda match: _mask_word(match.group(0), _visible_count(len(match.group(0)), strength)),
        value,
    )


def _normalize_title(value: str) -> str:
    compact = re.sub(r"\s+", "", value).lower()
    titles = {
        "mr": "Mr",
        "mrs": "Mrs",
        "ms": "Ms",
        "miss": "Miss",
        "dr": "Dr",
    }
    return titles.get(compact, value)


def _escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
