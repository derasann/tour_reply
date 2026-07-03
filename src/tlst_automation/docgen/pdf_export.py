"""PDF export via headless LibreOffice.

The generated xlsx keeps every sheet (予約情報 / 予約確認書(Oyster) / the
reference Sheet1 / Sheet2) in one editable master file, as requested --
but a client-facing Booking Confirmation PDF must not include the internal
sheets. `export_workbook_sheet_pdf` removes every sheet except the one
being exported in a throwaway copy before conversion, so the source
workbook file itself is untouched.

Marking the other sheets state="hidden" (rather than removing them) was
tried first and looks correct in the XML, but LibreOffice's headless
`--convert-to pdf` still renders at least one hidden sheet as an extra
page for this specific workbook (reproduced even after removing every
cross-sheet formula, so it isn't the formula-recalc dependency either --
most likely a quirk tied to this file's Google Sheets-authored metadata).
Physically removing the sheet's XML part is the reliable fix: LibreOffice
then has no way to render content that no longer exists in the archive.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import xlsx_lowlevel as xl

SOFFICE_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "soffice",
]

_SHEET_TAG_RE = re.compile(r"<sheet\b[^>]*/>")
_NAME_RE = re.compile(r'name="([^"]*)"')
_RID_RE = re.compile(r'r:id="([^"]*)"')
_RELATIONSHIP_RE = re.compile(r'<Relationship\b[^>]*/>')
_ID_RE = re.compile(r'Id="([^"]*)"')
_TARGET_RE = re.compile(r'Target="([^"]*)"')


class PdfExportError(RuntimeError):
    pass


def find_soffice() -> str:
    for candidate in SOFFICE_CANDIDATES:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    raise PdfExportError(
        "LibreOffice (soffice) not found. Install with: brew install --cask libreoffice"
    )


def convert_to_pdf(source_path: Path, output_dir: Path | None = None) -> Path:
    """Convert an xlsx/pptx/docx file to PDF via headless LibreOffice."""
    source_path = Path(source_path)
    output_dir = Path(output_dir) if output_dir else source_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    soffice = find_soffice()
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(source_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PdfExportError(f"soffice conversion failed: {result.stderr or result.stdout}")
    pdf_path = output_dir / (source_path.stem + ".pdf")
    if not pdf_path.exists():
        raise PdfExportError(f"expected {pdf_path} after conversion but it was not created")
    return pdf_path


def _remove_other_sheets(parts: dict[str, bytes], keep_sheet_name: str) -> None:
    """Mutates `parts` in place: drops every <sheet> except `keep_sheet_name`
    from workbook.xml, and removes the now-orphaned worksheet parts + their
    relationship/content-type entries, so LibreOffice has no way to render
    them at all.
    """
    workbook_xml = parts["xl/workbook.xml"].decode("utf-8")
    rels_xml = parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
    content_types_xml = parts["[Content_Types].xml"].decode("utf-8")

    kept_tag = None
    removed_rids: list[str] = []
    for match in _SHEET_TAG_RE.finditer(workbook_xml):
        tag = match.group(0)
        name_match = _NAME_RE.search(tag)
        if name_match and name_match.group(1) == keep_sheet_name:
            kept_tag = tag
            continue
        rid_match = _RID_RE.search(tag)
        if rid_match:
            removed_rids.append(rid_match.group(1))

    if kept_tag is None:
        raise ValueError(f"sheet {keep_sheet_name!r} not found in workbook.xml")

    workbook_xml = _SHEET_TAG_RE.sub(
        lambda m: kept_tag if m.group(0) == kept_tag else "", workbook_xml
    )

    removed_targets: list[str] = []
    for rid in removed_rids:
        rel_match = next(
            (m for m in _RELATIONSHIP_RE.finditer(rels_xml) if _ID_RE.search(m.group(0)) and _ID_RE.search(m.group(0)).group(1) == rid),
            None,
        )
        if rel_match is None:
            continue
        target_match = _TARGET_RE.search(rel_match.group(0))
        if target_match:
            removed_targets.append(target_match.group(1))
        rels_xml = rels_xml.replace(rel_match.group(0), "")

    for target in removed_targets:
        part_name = f"xl/{target}"
        parts.pop(part_name, None)
        rels_part_name = f"xl/{Path(target).parent}/_rels/{Path(target).name}.rels"
        parts.pop(rels_part_name, None)
        content_types_xml = content_types_xml.replace(
            f'<Override ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml" PartName="/{part_name}"/>',
            "",
        )

    parts["xl/workbook.xml"] = workbook_xml.encode("utf-8")
    parts["xl/_rels/workbook.xml.rels"] = rels_xml.encode("utf-8")
    parts["[Content_Types].xml"] = content_types_xml.encode("utf-8")


def export_workbook_sheet_pdf(xlsx_path: Path, sheet_name: str, output_path: Path) -> Path:
    """Export a single sheet of a multi-sheet workbook as a standalone PDF."""
    xlsx_path = Path(xlsx_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_xlsx = Path(tmp_dir) / xlsx_path.name
        parts = xl.load_zip_parts(xlsx_path)
        _remove_other_sheets(parts, sheet_name)
        xl.write_zip_parts(tmp_xlsx, parts)

        pdf_path = convert_to_pdf(tmp_xlsx, Path(tmp_dir))
        shutil.move(str(pdf_path), str(output_path))

    return output_path
