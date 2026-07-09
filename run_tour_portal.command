#!/bin/zsh
# どこに展開しても動くよう、このファイル自身の場所を基準にする。
cd "$(dirname "$0")"

# 古いシステムのpython3（例: 3.7）だと依存パッケージのインストールに失敗するため、
# 新しいバージョンを優先的に探し、3.9未満なら明確なエラーにする。
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; exit(0 if sys.version_info[:2] >= (3, 9) else 1)' 2>/dev/null; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "Python 3.9以降が見つかりませんでした。先にPython 3をインストールしてください。"
  echo "https://www.python.org/downloads/"
  read "?Enterキーで閉じます..."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "初回セットアップ中です（数分かかります）..."
  "$PYTHON_BIN" -m venv .venv || exit 1
  . .venv/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
else
  . .venv/bin/activate
fi

if [ ! -f "data/tours.db" ]; then
  echo "マスタデータ（サンプルのツアー・単価など）を準備しています..."
  PYTHONPATH=src python -m tlst_automation.seed
fi

if ! command -v soffice >/dev/null 2>&1 && [ ! -f "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
  echo "LibreOfficeが見つかりません。PDF書き出しには必要です。"
  echo "  brew install --cask libreoffice"
  echo "Excel/PowerPointの生成はLibreOfficeなしでも動きます。"
fi

PYTHONPATH=src streamlit run tour_portal_app.py
