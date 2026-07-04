#!/bin/zsh
# デスクトップなど別の場所に置いてもプロジェクト本体を見つけられるよう、
# $0 の場所ではなく実際のプロジェクトパスを直接指定しています。
cd "/Users/onoderakyoko/TLST_kaihatsu/tour_reply"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 が見つかりません。先に Python 3 をインストールしてください。"
  echo "https://www.python.org/downloads/"
  read "?Enterキーで閉じます..."
  exit 1
fi

if [ ! -d "venv311" ]; then
  echo "初回セットアップ中です..."
  python3 -m venv venv311 || exit 1
  . venv311/bin/activate
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
else
  . venv311/bin/activate
fi

if ! command -v soffice >/dev/null 2>&1 && [ ! -f "/Applications/LibreOffice.app/Contents/MacOS/soffice" ]; then
  echo "LibreOfficeが見つかりません。PDF書き出しには必要です。"
  echo "  brew install --cask libreoffice"
  echo "Excel/PowerPointの生成はLibreOfficeなしでも動きます。"
fi

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
fi

PYTHONPATH=src streamlit run tour_portal_app.py
