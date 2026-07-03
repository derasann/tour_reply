"""Minimal raw-XML cell editor for a specific xlsx template.

openpyxl round-trips (load_workbook -> save) silently drop the text runs
inside freeform drawing shapes (verified against templates/tour_workbook_template.xlsx:
14 <a:t> runs before, 0 after). Since the Booking Confirmation's Dietary /
Inclusions&Exclusions box is exactly that kind of shape, we can't use
openpyxl to write this file without losing it.

Instead we edit the handful of sheet-XML <c> (cell) and drawing-XML <a:t>
(text run) elements directly inside the zip, leaving every other part of
the archive (styles, charts, images, other shapes) untouched.

This is intentionally narrow: it only supports what this template needs
(inline string values, plain numbers, clearing a cell). It is not a
general-purpose OOXML writer.
"""

from __future__ import annotations

import re
import zipfile
from datetime import date
from pathlib import Path

EXCEL_EPOCH = date(1899, 12, 30)


def excel_date_serial(d: date) -> int:
    return (d - EXCEL_EPOCH).days


def excel_time_fraction(hour: int, minute: int) -> float:
    return (hour * 60 + minute) / (24 * 60)


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


_CELL_RE_TEMPLATE = r'<c r="{ref}"([^>]*?)(?:/>|>.*?</c>)'


def set_inline_string(xml: str, ref: str, value: str) -> str:
    pattern = re.compile(_CELL_RE_TEMPLATE.format(ref=re.escape(ref)), re.S)
    escaped = _escape_xml(value)

    def repl(match: re.Match[str]) -> str:
        attrs = re.sub(r'\s*t="[^"]*"', "", match.group(1))
        return f'<c r="{ref}"{attrs} t="inlineStr"><is><t xml:space="preserve">{escaped}</t></is></c>'

    new_xml, count = pattern.subn(repl, xml, count=1)
    if count == 0:
        raise ValueError(f"cell {ref} not found in sheet XML")
    return new_xml


def set_number(xml: str, ref: str, value: float | int) -> str:
    pattern = re.compile(_CELL_RE_TEMPLATE.format(ref=re.escape(ref)), re.S)

    def repl(match: re.Match[str]) -> str:
        attrs = re.sub(r'\s*t="[^"]*"', "", match.group(1))
        return f'<c r="{ref}"{attrs}><v>{value}</v></c>'

    new_xml, count = pattern.subn(repl, xml, count=1)
    if count == 0:
        raise ValueError(f"cell {ref} not found in sheet XML")
    return new_xml


def clear_cell(xml: str, ref: str) -> str:
    pattern = re.compile(_CELL_RE_TEMPLATE.format(ref=re.escape(ref)), re.S)

    def repl(match: re.Match[str]) -> str:
        attrs = re.sub(r'\s*t="[^"]*"', "", match.group(1))
        return f'<c r="{ref}"{attrs}/>'

    new_xml, count = pattern.subn(repl, xml, count=1)
    if count == 0:
        raise ValueError(f"cell {ref} not found in sheet XML")
    return new_xml


def replace_drawing_text_run(xml: str, index: int, value: str) -> str:
    """Replace the text of the Nth <a:t> run (0-based, document order)."""
    matches = list(re.finditer(r"<a:t>(.*?)</a:t>", xml, re.S))
    if index >= len(matches):
        raise IndexError(f"drawing has only {len(matches)} text runs, wanted index {index}")
    match = matches[index]
    escaped = _escape_xml(value)
    return xml[: match.start(1)] + escaped + xml[match.end(1) :]


def load_zip_parts(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as zin:
        return {name: zin.read(name) for name in zin.namelist()}


def write_zip_parts(path: Path, parts: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, content in parts.items():
            zout.writestr(name, content)
