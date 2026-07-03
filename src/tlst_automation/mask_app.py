from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .pdf_masker import mask_pdf


class MaskApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("TLST PDF Masker")
        self.geometry("620x340")
        self.minsize(560, 320)

        self.source_path = tk.StringVar()
        self.strength = tk.IntVar(value=3)
        self.status = tk.StringVar(value="PDFを選択するか、ファイルパスを貼り付けてください。")

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(root, text="PDF個人情報マスキング", font=("", 18, "bold"))
        title.pack(anchor=tk.W)

        lead = ttk.Label(
            root,
            text="Gmailから保存したPDFを匿名化PDFに変換します。元ファイルは変更しません。",
            wraplength=560,
        )
        lead.pack(anchor=tk.W, pady=(6, 16))

        path_frame = ttk.LabelFrame(root, text="元PDF")
        path_frame.pack(fill=tk.X)

        entry = ttk.Entry(path_frame, textvariable=self.source_path)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 6), pady=12)
        entry.bind("<Return>", lambda _event: self.run_masking())

        browse = ttk.Button(path_frame, text="選択", command=self.choose_file)
        browse.pack(side=tk.RIGHT, padx=(0, 10), pady=12)

        strength_frame = ttk.LabelFrame(root, text="マスキング強度")
        strength_frame.pack(fill=tk.X, pady=(14, 0))

        slider = ttk.Scale(
            strength_frame,
            from_=1,
            to=5,
            orient=tk.HORIZONTAL,
            variable=self.strength,
            command=lambda value: self.strength.set(round(float(value))),
        )
        slider.pack(fill=tk.X, padx=12, pady=(12, 2))

        labels = ttk.Frame(strength_frame)
        labels.pack(fill=tk.X, padx=12, pady=(0, 10))
        ttk.Label(labels, text="弱い").pack(side=tk.LEFT)
        ttk.Label(labels, text="標準").pack(side=tk.LEFT, expand=True)
        ttk.Label(labels, text="強い").pack(side=tk.RIGHT)

        actions = ttk.Frame(root)
        actions.pack(fill=tk.X, pady=(18, 0))
        ttk.Button(actions, text="マスクPDFを生成", command=self.run_masking).pack(side=tk.RIGHT)

        status = ttk.Label(root, textvariable=self.status, wraplength=560)
        status.pack(anchor=tk.W, pady=(14, 0))

    def choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="マスクするPDFを選択",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if path:
            self.source_path.set(path)

    def run_masking(self) -> None:
        raw_path = self.source_path.get().strip().strip('"').strip("'")
        if raw_path.startswith("{") and raw_path.endswith("}"):
            raw_path = raw_path[1:-1]
        source = Path(raw_path).expanduser()
        if not source.exists() or source.suffix.lower() != ".pdf":
            messagebox.showerror("PDFが見つかりません", "有効なPDFファイルを選択してください。")
            return

        self.status.set("生成中です...")
        thread = threading.Thread(target=self._mask_in_background, args=(source,), daemon=True)
        thread.start()

    def _mask_in_background(self, source: Path) -> None:
        try:
            output = mask_pdf(source, strength=self.strength.get())
        except Exception as exc:  # pragma: no cover - GUI safety net
            self.after(0, lambda: self._show_error(exc))
            return
        self.after(0, lambda: self._show_success(output))

    def _show_success(self, output: Path) -> None:
        self.status.set(f"生成しました: {output}")
        messagebox.showinfo("完了", f"マスク済みPDFを生成しました。\n\n{output}")

    def _show_error(self, exc: Exception) -> None:
        self.status.set("生成に失敗しました。")
        messagebox.showerror("エラー", str(exc))


def main() -> None:
    app = MaskApp()
    app.mainloop()


if __name__ == "__main__":
    main()
