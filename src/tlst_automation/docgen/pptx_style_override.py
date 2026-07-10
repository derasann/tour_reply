"""Per-tour layout ("style") overrides for the guide-request PPTX itinerary
table, mirroring docgen/style_override.py's xlsx mechanism but using the
PPTX table's own XML shape.

Unlike xlsx (styles live in a separate styles.xml, referenced by index),
each PPTX table cell (<a:tc>) carries its own self-contained <a:tcPr>
element covering fill/borders/margins, right next to its <a:txBody> text
content. That makes diff/reapply simpler here: capture whichever cells'
<a:tcPr> differ from the shared template, and splice those blocks back
onto the corresponding cells of a freshly generated file -- no shared
style-table bookkeeping needed.

Cell values are read only to walk the (row, col) grid; nothing derived
from booking/customer content is ever stored, only the tcPr styling.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

SLIDE_PART = "ppt/slides/slide1.xml"
TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "templates" / "guide_request_template.pptx"
)

_TBL_RE = re.compile(r"<a:tbl>.*?</a:tbl>", re.S)
_ROW_RE = re.compile(r"<a:tr\b[^>]*>.*?</a:tr>", re.S)
_CELL_RE = re.compile(r"<a:tc\b[^>]*>.*?</a:tc>|<a:tc\b[^>]*/>", re.S)
_TCPR_RE = re.compile(r"<a:tcPr\b[^>]*>.*?</a:tcPr>|<a:tcPr\b[^>]*/>", re.S)
_GRID_RE = re.compile(r"<a:tblGrid>.*?</a:tblGrid>", re.S)
_GRIDCOL_RE = re.compile(r"<a:gridCol\b[^>]*(?:/>|>.*?</a:gridCol>)", re.S)
_ROW_HEIGHT_RE = re.compile(r'<a:tr h="(\d+)"')


def _load_zip(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as zin:
        return {name: zin.read(name) for name in zin.namelist()}


def _write_zip(path: Path, parts: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, content in parts.items():
            zout.writestr(name, content)


def _replace_spans(original: str, replacements: list[tuple[int, int, str]]) -> str:
    """Apply non-overlapping (start, end, new_text) replacements to
    `original` by position, not by content match -- itinerary rows are
    often byte-identical (unused rows all share the same blank styling),
    so a naive str.replace() would risk patching the wrong occurrence."""
    if not replacements:
        return original
    replacements = sorted(replacements, key=lambda r: r[0])
    pieces = []
    last_end = 0
    for start, end, new_text in replacements:
        pieces.append(original[last_end:start])
        pieces.append(new_text)
        last_end = end
    pieces.append(original[last_end:])
    return "".join(pieces)


def _col_widths(tbl_xml: str) -> list[int]:
    grid_match = _GRID_RE.search(tbl_xml)
    if not grid_match:
        return []
    return [int(w) for w in re.findall(r'w="(\d+)"', grid_match.group(0))]


class StyleDiffError(ValueError):
    pass


def capture_style_diff(fixed_path: str | Path) -> dict:
    """Diff `fixed_path` (a user's manually-corrected copy of a generated
    guide-request PPTX) against the shared base template's itinerary
    table, cell by cell, and return only what differs: cell tcPr blocks
    (fill/border/margins), column widths, and row heights.

    Cells are matched purely by (row index, column index) in table order,
    since PPTX table cells don't carry any stable ID of their own. That
    only stays correct if the fixed file has the exact same table shape
    as the template it was generated from -- if rows were added/deleted/
    merged differently while "fixing" it in PowerPoint (e.g. deleting the
    template's many unused blank itinerary rows), every row after the
    change lines up with the wrong template row, silently producing a
    diff that misapplies borders/fills to the wrong cells later. Raise
    instead of returning a subtly-wrong diff.
    """
    base_parts = _load_zip(TEMPLATE_PATH)
    fixed_parts = _load_zip(Path(fixed_path))
    base_slide = base_parts[SLIDE_PART].decode("utf-8")
    fixed_slide = fixed_parts[SLIDE_PART].decode("utf-8")

    base_tbl_match = _TBL_RE.search(base_slide)
    fixed_tbl_match = _TBL_RE.search(fixed_slide)
    if not base_tbl_match or not fixed_tbl_match:
        return {"cells": {}, "col_widths": {}, "row_heights": {}}
    base_tbl, fixed_tbl = base_tbl_match.group(0), fixed_tbl_match.group(0)

    base_rows = [m.group(0) for m in _ROW_RE.finditer(base_tbl)]
    fixed_rows = [m.group(0) for m in _ROW_RE.finditer(fixed_tbl)]

    if len(base_rows) != len(fixed_rows):
        raise StyleDiffError(
            f"行程表の行数がテンプレートと異なります（テンプレート{len(base_rows)}行 / "
            f"アップロードされたファイル{len(fixed_rows)}行）。PowerPoint上で行の追加・削除・"
            "結合を行わず、色や罫線などの見た目だけを変更してから再度アップロードしてください。"
        )

    cells: dict[str, str] = {}
    for row_idx, (base_row, fixed_row) in enumerate(zip(base_rows, fixed_rows)):
        base_cells = [m.group(0) for m in _CELL_RE.finditer(base_row)]
        fixed_cells = [m.group(0) for m in _CELL_RE.finditer(fixed_row)]
        if len(base_cells) != len(fixed_cells):
            raise StyleDiffError(
                f"行程表の{row_idx + 1}行目の列数がテンプレートと異なります。PowerPoint上でセルの結合・"
                "分割を行わず、色や罫線などの見た目だけを変更してから再度アップロードしてください。"
            )
        for col_idx, (base_cell, fixed_cell) in enumerate(zip(base_cells, fixed_cells)):
            base_tcpr_match = _TCPR_RE.search(base_cell)
            fixed_tcpr_match = _TCPR_RE.search(fixed_cell)
            base_tcpr = base_tcpr_match.group(0) if base_tcpr_match else ""
            fixed_tcpr = fixed_tcpr_match.group(0) if fixed_tcpr_match else ""
            if base_tcpr != fixed_tcpr:
                cells[f"{row_idx}:{col_idx}"] = fixed_tcpr

    base_widths = _col_widths(base_tbl)
    fixed_widths = _col_widths(fixed_tbl)
    col_widths = {
        str(i): fw for i, (bw, fw) in enumerate(zip(base_widths, fixed_widths)) if bw != fw
    }

    row_heights: dict[str, str] = {}
    for row_idx, (base_row, fixed_row) in enumerate(zip(base_rows, fixed_rows)):
        base_h_match = _ROW_HEIGHT_RE.match(base_row)
        fixed_h_match = _ROW_HEIGHT_RE.match(fixed_row)
        base_h = base_h_match.group(1) if base_h_match else None
        fixed_h = fixed_h_match.group(1) if fixed_h_match else None
        if fixed_h is not None and fixed_h != base_h:
            row_heights[str(row_idx)] = fixed_h

    return {"cells": cells, "col_widths": col_widths, "row_heights": row_heights}


def apply_style_diff(pptx_path: str | Path, diff: dict) -> None:
    """Apply a previously-captured style diff onto a freshly-generated
    guide-request PPTX. Best-effort: a saved cell/row/column reference that
    no longer matches the current table shape is skipped rather than
    raising, since this is a cosmetic enhancement, not a required step."""
    pptx_path = Path(pptx_path)
    parts = _load_zip(pptx_path)
    slide = parts[SLIDE_PART].decode("utf-8")

    tbl_match = _TBL_RE.search(slide)
    if not tbl_match:
        return
    tbl_xml = tbl_match.group(0)

    cell_overrides = diff.get("cells", {})
    row_height_overrides = diff.get("row_heights", {})

    row_matches = list(_ROW_RE.finditer(tbl_xml))
    row_replacements: list[tuple[int, int, str]] = []
    for row_idx, row_match in enumerate(row_matches):
        row_xml = row_match.group(0)
        cell_matches = list(_CELL_RE.finditer(row_xml))
        cell_replacements: list[tuple[int, int, str]] = []
        for col_idx, cell_match in enumerate(cell_matches):
            new_tcpr = cell_overrides.get(f"{row_idx}:{col_idx}")
            if new_tcpr is None:
                continue
            tcpr_match = _TCPR_RE.search(cell_match.group(0))
            if tcpr_match:
                cell_replacements.append(
                    (cell_match.start() + tcpr_match.start(), cell_match.start() + tcpr_match.end(), new_tcpr)
                )
            elif new_tcpr:
                insert_at = cell_match.end() - len("</a:tc>")
                cell_replacements.append((insert_at, insert_at, new_tcpr))

        new_row_xml = _replace_spans(row_xml, cell_replacements)

        new_height = row_height_overrides.get(str(row_idx))
        if new_height:
            height_match = _ROW_HEIGHT_RE.match(new_row_xml)
            if height_match:
                new_row_xml = f'<a:tr h="{new_height}"' + new_row_xml[height_match.end() :]

        if new_row_xml != row_xml:
            row_replacements.append((row_match.start(), row_match.end(), new_row_xml))

    new_tbl_xml = _replace_spans(tbl_xml, row_replacements)

    col_width_overrides = diff.get("col_widths", {})
    if col_width_overrides:
        grid_match = _GRID_RE.search(new_tbl_xml)
        if grid_match:
            grid_xml = grid_match.group(0)
            col_matches = list(_GRIDCOL_RE.finditer(grid_xml))
            col_replacements: list[tuple[int, int, str]] = []
            for col_idx_str, width in col_width_overrides.items():
                idx = int(col_idx_str)
                if idx >= len(col_matches):
                    continue
                col_xml = col_matches[idx].group(0)
                width_match = re.search(r'w="\d+"', col_xml)
                if width_match:
                    col_replacements.append(
                        (
                            col_matches[idx].start() + width_match.start(),
                            col_matches[idx].start() + width_match.end(),
                            f'w="{width}"',
                        )
                    )
            new_grid_xml = _replace_spans(grid_xml, col_replacements)
            if new_grid_xml != grid_xml:
                new_tbl_xml = new_tbl_xml[: grid_match.start()] + new_grid_xml + new_tbl_xml[grid_match.end() :]

    new_slide = slide[: tbl_match.start()] + new_tbl_xml + slide[tbl_match.end() :]
    parts[SLIDE_PART] = new_slide.encode("utf-8")
    _write_zip(pptx_path, parts)
