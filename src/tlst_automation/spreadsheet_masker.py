from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from .pdf_masker import mask_text


GOOGLE_SHEETS_RE = re.compile(r"/spreadsheets/d/([^/]+)")
COMPANY_LABELS = ("一般社団法人", "株式会社", "有限会社", "合同会社")
COMPANY_PREFIX_RE = re.compile(r"(一般社団法人|株式会社|有限会社|合同会社)([一-龥ぁ-んァ-ヴーA-Za-z0-9・ー]{3,})")
COMPANY_SUFFIX_RE = re.compile(r"([一-龥ぁ-んァ-ヴーA-Za-z0-9・ー]{3,})(株式会社|有限会社|合同会社)")
JAPANESE_TOKEN_RE = re.compile(r"[一-龥ぁ-んァ-ヴー]{3,}")


@dataclass(frozen=True)
class MaskedSheetResult:
    source_url: str
    download_url: str
    original_path: Path
    masked_path: Path
    original_preview: str
    masked_preview: str


def mask_sheet_url(
    sheet_url: str,
    output_dir: str | Path,
    *,
    strength: int = 3,
    save_original: bool = True,
) -> MaskedSheetResult:
    output = Path(output_dir).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    download_url = to_csv_export_url(sheet_url)
    base_name = _safe_sheet_name(sheet_url)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    original_path = _next_output_path(output / f"{base_name}_{stamp}_original.csv")
    masked_path = _next_output_path(output / f"{base_name}_{stamp}_masked.csv")

    csv_text = download_csv_text(download_url)
    masked_text = mask_csv_text(csv_text, strength=strength)

    if save_original:
        original_path.write_text(csv_text, encoding="utf-8-sig", newline="")
    else:
        original_path = Path("")
    masked_path.write_text(masked_text, encoding="utf-8-sig", newline="")

    return MaskedSheetResult(
        source_url=sheet_url,
        download_url=download_url,
        original_path=original_path,
        masked_path=masked_path,
        original_preview=_preview(csv_text),
        masked_preview=_preview(masked_text),
    )


def to_csv_export_url(sheet_url: str) -> str:
    parsed = urlparse(sheet_url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Spreadsheet URL is required")

    match = GOOGLE_SHEETS_RE.search(parsed.path)
    if not match:
        return sheet_url.strip()

    spreadsheet_id = match.group(1)
    query = parse_qs(parsed.query)
    gid = query.get("gid", ["0"])[0]
    fragment_query = parse_qs(parsed.fragment)
    gid = fragment_query.get("gid", [gid])[0]
    params = urlencode({"format": "csv", "gid": gid})
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?{params}"


def download_csv_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "TLSTMasker/1.0",
            "Accept": "text/csv,text/plain,application/octet-stream,*/*",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type.lower():
                raise ValueError(
                    "Could not download CSV. The sheet may require login or may not be shared for link access."
                )
    except HTTPError as exc:
        raise ValueError(f"Could not download CSV: HTTP {exc.code}") from exc
    except URLError as exc:
        raise ValueError(f"Could not download CSV: {exc.reason}") from exc

    return _decode_csv_bytes(data)


def mask_csv_text(csv_text: str, *, strength: int = 3) -> str:
    source = StringIO(csv_text)
    output = StringIO()
    reader = csv.reader(source)
    writer = csv.writer(output, lineterminator="\n")
    for row in reader:
        writer.writerow([mask_spreadsheet_cell(cell, strength=strength) for cell in row])
    return output.getvalue()


def mask_spreadsheet_cell(cell: str, *, strength: int = 3) -> str:
    masked = mask_text(cell, strength=strength)
    if strength < 5:
        return masked

    masked = COMPANY_PREFIX_RE.sub(
        lambda match: match.group(1) + _mask_compact_value(match.group(2), keep_start=1, keep_end=0),
        masked,
    )
    masked = COMPANY_SUFFIX_RE.sub(
        lambda match: _mask_compact_value(match.group(1), keep_start=1, keep_end=0) + match.group(2),
        masked,
    )
    masked = JAPANESE_TOKEN_RE.sub(
        lambda match: _mask_japanese_token(match.group(0)),
        masked,
    )
    return masked


def _decode_csv_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _safe_sheet_name(sheet_url: str) -> str:
    parsed = urlparse(sheet_url.strip())
    match = GOOGLE_SHEETS_RE.search(parsed.path)
    if match:
        return "google_sheet"
    name = Path(unquote(parsed.path)).stem or "spreadsheet"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    return safe or "spreadsheet"


def _preview(text: str, *, limit: int = 8000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... preview truncated ..."


def _mask_compact_value(value: str, *, keep_start: int, keep_end: int) -> str:
    if len(value) <= keep_start + keep_end:
        return "*" * len(value)
    middle = len(value) - keep_start - keep_end
    return value[:keep_start] + "*" * middle + (value[-keep_end:] if keep_end else "")


def _mask_japanese_token(value: str) -> str:
    for label in COMPANY_LABELS:
        if value == label:
            return value
        if value.startswith(label):
            rest = value[len(label) :]
            if len(rest) <= 1:
                return value
            return label + _mask_compact_value(rest, keep_start=1, keep_end=0)
    return _mask_compact_value(value, keep_start=1, keep_end=1)


def _next_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("Too many masked spreadsheet files with the same name")
