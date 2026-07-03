from __future__ import annotations

import cgi
import json
import threading
import tempfile
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .pdf_masker import extract_pdf_text, mask_text, write_text_pdf
from .spreadsheet_masker import mask_sheet_url

HOST = "127.0.0.1"
PORT = 8765
OUTPUT_DIR = Path.cwd() / "masked_outputs"
DOWNLOADS: dict[str, Path] = {}

HTML = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TLST PDF Masker</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", sans-serif; margin: 0; background: #f7f7f4; color: #222; }
    main { max-width: 920px; margin: 48px auto; padding: 0 20px; }
    h1 { font-size: 28px; margin: 0 0 8px; }
    p { line-height: 1.7; color: #555; }
    #drop { border: 2px dashed #8b8f76; background: #fff; min-height: 180px; display: grid; place-items: center; padding: 24px; text-align: center; border-radius: 8px; transition: .15s ease; }
    #drop.drag { border-color: #1f6f68; background: #eef7f5; }
    .row { margin-top: 22px; background: #fff; padding: 18px; border-radius: 8px; }
    input[type="range"], input[type="text"], input[type="url"], select { box-sizing: border-box; width: 100%; }
    input[type="text"], input[type="url"], select { border: 1px solid #d7d7cd; border-radius: 6px; padding: 10px; font-size: 14px; background: #fbfbf8; }
    button { appearance: none; border: 0; background: #1f6f68; color: #fff; border-radius: 6px; padding: 12px 18px; font-size: 15px; cursor: pointer; }
    button:disabled { background: #9aa3a0; cursor: wait; }
    textarea { box-sizing: border-box; width: 100%; min-height: 220px; border: 1px solid #d7d7cd; border-radius: 6px; padding: 12px; font: 13px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; resize: vertical; background: #fbfbf8; }
    .preview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .preview-grid h2 { margin: 0 0 10px; font-size: 16px; }
    .settings-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
    .checkbox { display: inline-flex; align-items: center; gap: 8px; margin-top: 12px; color: #444; }
    .muted { font-size: 13px; color: #777; }
    .path { overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; background: #f2f2ec; padding: 10px; border-radius: 6px; }
    #status { margin-top: 16px; font-weight: 600; }
    #download { display: none; margin-top: 12px; color: #1f6f68; font-weight: 600; }
    @media (max-width: 720px) { .preview-grid, .settings-grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <h1>TLST 個人情報マスキング</h1>
  <p>PDFの匿名化に加えて、Google SheetsのURLから予約表をCSVで取得し、マスク済みCSVをデスクトップへ生成できます。元ファイルは変更しません。</p>
  <div id="drop">
    <div>
      <strong>PDFをここにドラッグ</strong>
      <p class="muted">またはクリックしてPDFを選択</p>
      <input id="file" type="file" accept="application/pdf" hidden>
      <div id="filename" class="muted"></div>
    </div>
  </div>
  <div class="row">
    <label for="strength">マスキング強度: <span id="strengthLabel">3</span></label>
    <input id="strength" type="range" min="1" max="5" value="3">
    <p class="muted">1は弱め、5は強めです。迷ったら3がおすすめです。</p>
  </div>
  <div class="row settings-grid">
    <section>
      <label for="outputPreset"><strong>保存先</strong></label>
      <select id="outputPreset">
        <option value="desktop" selected>デスクトップ</option>
        <option value="downloads">ダウンロード</option>
        <option value="documents">書類</option>
        <option value="app">アプリ内 masked_outputs</option>
        <option value="custom">カスタム</option>
      </select>
      <p class="muted">会社の方のPCでは、その方のユーザーのフォルダに保存されます。</p>
    </section>
    <section>
      <label for="customOutputDir"><strong>カスタム保存先</strong></label>
      <input id="customOutputDir" type="text" placeholder="/Users/name/Desktop/共有用 など" disabled>
      <p class="muted">カスタムを選んだ時だけ使います。存在しないフォルダは作成します。</p>
    </section>
  </div>
  <div class="row">
    <div class="actions">
      <button id="preview" disabled>プレビューを表示</button>
      <button id="run" disabled>マスクPDFを生成</button>
    </div>
    <div id="status"></div>
    <a id="download" href="#">生成PDFを開く / ダウンロード</a>
  </div>
  <div class="row">
    <strong>生成PDFの保存先</strong>
    <div id="outputPath" class="path muted">まだ生成されていません。</div>
  </div>
  <div class="row preview-grid">
    <section>
      <h2>抽出テキストのプレビュー</h2>
      <textarea id="extractedPreview" readonly placeholder="プレビュー表示後に表示されます。"></textarea>
    </section>
    <section>
      <h2>マスク後テキストのプレビュー</h2>
      <textarea id="maskedPreview" readonly placeholder="プレビュー表示後に表示されます。"></textarea>
    </section>
  </div>
  <div class="row">
    <h2>スプレッドシートURLからマスクCSVを作成</h2>
    <p class="muted">Google SheetsのURLを貼ると、表示中のシートをCSVとして取得し、元CSVとマスク済みCSVを保存先に出力します。リンク共有で閲覧できるシートが対象です。</p>
    <label for="sheetUrl"><strong>Google Sheets URL</strong></label>
    <input id="sheetUrl" type="url" placeholder="https://docs.google.com/spreadsheets/d/.../edit#gid=0">
    <label class="checkbox">
      <input id="saveOriginalCsv" type="checkbox" checked>
      元CSVもデスクトップに保存する
    </label>
    <div class="actions" style="margin-top: 14px;">
      <button id="sheetRun">スプレッドシートを取得してマスクCSVを生成</button>
    </div>
    <div id="sheetStatus"></div>
    <div style="margin-top: 12px;">
      <strong>元CSVの保存先</strong>
      <div id="sheetOriginalPath" class="path muted">まだ生成されていません。</div>
    </div>
    <div style="margin-top: 12px;">
      <strong>マスク済みCSVの保存先</strong>
      <div id="sheetMaskedPath" class="path muted">まだ生成されていません。</div>
      <a id="sheetDownload" href="#" style="display: none; margin-top: 12px; color: #1f6f68; font-weight: 600;">マスク済みCSVを開く / ダウンロード</a>
    </div>
  </div>
  <div class="row preview-grid">
    <section>
      <h2>取得CSVのプレビュー</h2>
      <textarea id="sheetOriginalPreview" readonly placeholder="生成後に表示されます。"></textarea>
    </section>
    <section>
      <h2>マスク済みCSVのプレビュー</h2>
      <textarea id="sheetMaskedPreview" readonly placeholder="生成後に表示されます。"></textarea>
    </section>
  </div>
</main>
<script>
const drop = document.getElementById("drop");
const fileInput = document.getElementById("file");
const filename = document.getElementById("filename");
const preview = document.getElementById("preview");
const run = document.getElementById("run");
const strength = document.getElementById("strength");
const strengthLabel = document.getElementById("strengthLabel");
const outputPreset = document.getElementById("outputPreset");
const customOutputDir = document.getElementById("customOutputDir");
const status = document.getElementById("status");
const outputPath = document.getElementById("outputPath");
const extractedPreview = document.getElementById("extractedPreview");
const maskedPreview = document.getElementById("maskedPreview");
const download = document.getElementById("download");
const sheetUrl = document.getElementById("sheetUrl");
const saveOriginalCsv = document.getElementById("saveOriginalCsv");
const sheetRun = document.getElementById("sheetRun");
const sheetStatus = document.getElementById("sheetStatus");
const sheetOriginalPath = document.getElementById("sheetOriginalPath");
const sheetMaskedPath = document.getElementById("sheetMaskedPath");
const sheetOriginalPreview = document.getElementById("sheetOriginalPreview");
const sheetMaskedPreview = document.getElementById("sheetMaskedPreview");
const sheetDownload = document.getElementById("sheetDownload");
let selectedFile = null;

function setFile(file) {
  selectedFile = file;
  filename.textContent = file ? file.name : "";
  preview.disabled = !file;
  run.disabled = !file;
  status.textContent = "";
  outputPath.textContent = "まだ生成されていません。";
  extractedPreview.value = "";
  maskedPreview.value = "";
  download.style.display = "none";
  download.removeAttribute("href");
}

drop.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => setFile(fileInput.files[0]));
strength.addEventListener("input", () => strengthLabel.textContent = strength.value);
strength.addEventListener("change", () => {
  outputPath.textContent = "まだ生成されていません。";
  download.style.display = "none";
  download.removeAttribute("href");
});
outputPreset.addEventListener("change", () => {
  customOutputDir.disabled = outputPreset.value !== "custom";
  outputPath.textContent = "まだ生成されていません。";
  download.style.display = "none";
  download.removeAttribute("href");
});

["dragenter", "dragover"].forEach(name => drop.addEventListener(name, event => {
  event.preventDefault();
  drop.classList.add("drag");
}));
["dragleave", "drop"].forEach(name => drop.addEventListener(name, event => {
  event.preventDefault();
  drop.classList.remove("drag");
}));
drop.addEventListener("drop", event => setFile(event.dataTransfer.files[0]));

function buildFormData() {
  const data = new FormData();
  data.append("pdf", selectedFile);
  data.append("strength", strength.value);
  data.append("output_preset", outputPreset.value);
  data.append("custom_output_dir", customOutputDir.value);
  return data;
}

function showPreview(result) {
  extractedPreview.value = result.extracted_text || "";
  maskedPreview.value = result.masked_text || "";
}

preview.addEventListener("click", async () => {
  if (!selectedFile) return;
  preview.disabled = true;
  run.disabled = true;
  status.textContent = "プレビュー作成中です...";
  outputPath.textContent = "まだ生成されていません。";
  download.style.display = "none";
  download.removeAttribute("href");
  const response = await fetch("/preview", { method: "POST", body: buildFormData() });
  if (!response.ok) {
    status.textContent = await response.text();
    preview.disabled = false;
    run.disabled = false;
    return;
  }
  const result = await response.json();
  showPreview(result);
  status.textContent = "プレビューを表示しました。問題なければPDFを生成してください。";
  preview.disabled = false;
  run.disabled = false;
});

run.addEventListener("click", async () => {
  if (!selectedFile) return;
  preview.disabled = true;
  run.disabled = true;
  status.textContent = "生成中です...";
  const response = await fetch("/mask", { method: "POST", body: buildFormData() });
  if (!response.ok) {
    status.textContent = await response.text();
    preview.disabled = false;
    run.disabled = false;
    return;
  }
  const result = await response.json();
  showPreview(result);
  outputPath.textContent = result.output_path || "";
  download.href = result.download_url;
  download.download = result.output_filename;
  download.style.display = "inline-block";
  status.textContent = "生成しました。プレビューを確認してからPDFを共有してください。";
  preview.disabled = false;
  run.disabled = false;
});

sheetRun.addEventListener("click", async () => {
  const url = sheetUrl.value.trim();
  if (!url) {
    sheetStatus.textContent = "Google Sheets URLを入力してください。";
    return;
  }
  sheetRun.disabled = true;
  sheetStatus.textContent = "スプレッドシートを取得してマスク中です...";
  sheetOriginalPath.textContent = "生成中です...";
  sheetMaskedPath.textContent = "生成中です...";
  sheetDownload.style.display = "none";
  sheetDownload.removeAttribute("href");

  const data = new FormData();
  data.append("sheet_url", url);
  data.append("strength", strength.value);
  data.append("output_preset", outputPreset.value);
  data.append("custom_output_dir", customOutputDir.value);
  data.append("save_original", saveOriginalCsv.checked ? "1" : "0");

  const response = await fetch("/sheet-mask", { method: "POST", body: data });
  if (!response.ok) {
    sheetStatus.textContent = await response.text();
    sheetOriginalPath.textContent = "まだ生成されていません。";
    sheetMaskedPath.textContent = "まだ生成されていません。";
    sheetRun.disabled = false;
    return;
  }
  const result = await response.json();
  sheetOriginalPath.textContent = result.original_path || "保存しない設定です。";
  sheetMaskedPath.textContent = result.masked_path || "";
  sheetOriginalPreview.value = result.original_preview || "";
  sheetMaskedPreview.value = result.masked_preview || "";
  sheetDownload.href = result.download_url;
  sheetDownload.download = result.output_filename;
  sheetDownload.style.display = "inline-block";
  sheetStatus.textContent = "生成しました。マスク済みCSVをこのチャットに渡す時は、保存先のファイルを添付してください。";
  sheetRun.disabled = false;
});
</script>
</body>
</html>
"""


class MaskHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/download":
            token = parse_qs(parsed.query).get("token", [""])[0]
            download_path = DOWNLOADS.get(token)
            if download_path is None or not download_path.exists():
                self.send_error(404)
                return
            filename = download_path.name
            data = download_path.read_bytes()
            self.send_response(200)
            content_type = "text/csv; charset=utf-8" if download_path.suffix.lower() == ".csv" else "application/pdf"
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/sheet-mask":
            self._handle_sheet_mask()
            return

        if self.path not in {"/preview", "/mask"}:
            self.send_error(404)
            return

        try:
            source_name, extracted_text, masked_text = self._preview_texts()
        except ValueError as exc:
            self.send_error(400, str(exc))
            return

        result = {
            "extracted_text": extracted_text,
            "masked_text": masked_text,
        }
        if self.path == "/mask":
            try:
                output_dir = self._resolve_output_dir()
            except ValueError as exc:
                self.send_error(400, str(exc))
                return
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                output = _next_output_path(output_dir / f"{Path(source_name).stem}_masked.pdf")
                write_text_pdf(masked_text, output)
            except OSError as exc:
                self.send_error(400, f"Could not write PDF to output folder: {exc}")
                return
            token = uuid.uuid4().hex
            DOWNLOADS[token] = output
            result.update(
                {
                    "output_path": str(output),
                    "output_filename": output.name,
                    "download_url": f"/download?token={token}",
                }
            )
        data = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8")

    def _handle_sheet_mask(self) -> None:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                "CONTENT_LENGTH": self.headers.get("Content-Length", ""),
            },
        )
        sheet_url = form.getfirst("sheet_url", "").strip()
        if not sheet_url:
            self.send_error(400, "Google Sheets URL is required")
            return
        strength = int(form.getfirst("strength", "3"))
        self._output_preset = form.getfirst("output_preset", "desktop")
        self._custom_output_dir = form.getfirst("custom_output_dir", "")
        save_original = form.getfirst("save_original", "1") == "1"
        try:
            output_dir = self._resolve_output_dir()
            result = mask_sheet_url(
                sheet_url,
                output_dir,
                strength=strength,
                save_original=save_original,
            )
        except ValueError as exc:
            self.send_error(400, str(exc))
            return
        except OSError as exc:
            self.send_error(400, f"Could not write CSV to output folder: {exc}")
            return

        token = uuid.uuid4().hex
        DOWNLOADS[token] = result.masked_path
        payload = {
            "download_url": f"/download?token={token}",
            "output_filename": result.masked_path.name,
            "original_path": str(result.original_path) if result.original_path else "",
            "masked_path": str(result.masked_path),
            "original_preview": result.original_preview,
            "masked_preview": result.masked_preview,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _resolve_output_dir(self) -> Path:
        preset = getattr(self, "_output_preset", "desktop")
        custom_output_dir = getattr(self, "_custom_output_dir", "")
        home = Path.home()
        presets = {
            "desktop": home / "Desktop",
            "downloads": home / "Downloads",
            "documents": home / "Documents",
            "app": OUTPUT_DIR,
        }
        if preset == "custom":
            if not custom_output_dir.strip():
                raise ValueError("Custom output folder is required")
            return Path(custom_output_dir).expanduser()
        return presets.get(preset, home / "Desktop")

    def _preview_texts(self) -> tuple[str, str, str]:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                "CONTENT_LENGTH": self.headers.get("Content-Length", ""),
            },
        )
        file_item = form["pdf"] if "pdf" in form else None
        if file_item is None or not file_item.filename:
            raise ValueError("PDF file is required")

        strength = int(form.getfirst("strength", "3"))
        self._output_preset = form.getfirst("output_preset", "desktop")
        self._custom_output_dir = form.getfirst("custom_output_dir", "")
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / Path(file_item.filename).name
            source.write_bytes(file_item.file.read())
            extracted_text = extract_pdf_text(source)
            masked_text = mask_text(extracted_text, strength=strength)
        return Path(file_item.filename).name, extracted_text, masked_text


def _next_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("Too many masked PDF files with the same name")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MaskHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"TLST PDF Masker: {url}", flush=True)
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    server.serve_forever()


if __name__ == "__main__":
    main()
