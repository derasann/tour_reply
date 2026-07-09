#!/bin/zsh
# 社内の他の人（Mac/Windows）に使用感を試してもらうための一時共有zipを作成する。
# .env に入っている Anthropic API キーをそのまま同梱するので、
# 出来上がった zip の扱いには注意すること（README参照）。
cd "$(dirname "$0")"

ZIP_NAME="TLST_Tour_Portal_Share.zip"
STAGING_DIR="TLST_Tour_Portal_Share"

if [ ! -f ".env" ]; then
  echo ".env が見つかりません（ANTHROPIC_API_KEY が必要です）。"
  exit 1
fi

API_KEY=$(grep '^ANTHROPIC_API_KEY=' .env | head -1 | cut -d= -f2-)
if [ -z "$API_KEY" ]; then
  echo ".env に ANTHROPIC_API_KEY が見つかりませんでした。"
  exit 1
fi

rm -rf "$STAGING_DIR" "$ZIP_NAME"
mkdir -p "$STAGING_DIR/.streamlit"
mkdir -p "$STAGING_DIR/pages"
mkdir -p "$STAGING_DIR/templates"

cp run_tour_portal.command "$STAGING_DIR/"
cp run_tour_portal_windows.bat "$STAGING_DIR/"
cp requirements.txt "$STAGING_DIR/"
cp tour_portal_app.py "$STAGING_DIR/"
cp portal_common.py "$STAGING_DIR/"

# tour_portal_app.py の st.page_link は元の日本語ファイル名を直接参照しているので、
# 上でリネームしたページファイル名に合わせて書き換える。
sed -i '' \
  -e 's#pages/1_新規登録\.py#pages/1_New_Booking.py#' \
  -e 's#pages/2_マスタ管理\.py#pages/2_Master_Data.py#' \
  "$STAGING_DIR/tour_portal_app.py"
cp templates/*.xlsx templates/*.pptx "$STAGING_DIR/templates/"
cp TOUR_PORTAL_SHARE_README.md "$STAGING_DIR/README.md"

# pages/ はファイル名（日本語）がそのままStreamlitのサイドバー表示名になるが、
# zipのファイル名エンコーディング(UTF-8フラグ)がWindows展開時に化ける事例があるため、
# 共有用パッケージだけ英語のASCIIファイル名に変えておく（サイドバー表示は英語になる）。
cp pages/1_*.py "$STAGING_DIR/pages/1_New_Booking.py"
cp pages/2_*.py "$STAGING_DIR/pages/2_Master_Data.py"

# src/tlst_automation 一式（__pycache__・.DS_Store は除く）
mkdir -p "$STAGING_DIR/src"
rsync -a --exclude="__pycache__" --exclude=".DS_Store" src/tlst_automation "$STAGING_DIR/src/"

cat > "$STAGING_DIR/.streamlit/secrets.toml" <<EOF
anthropic_api_key = "${API_KEY}"
EOF

chmod +x "$STAGING_DIR/run_tour_portal.command"

zip -r "$ZIP_NAME" "$STAGING_DIR" >/dev/null
rm -rf "$STAGING_DIR"

echo "作成しました: $ZIP_NAME"
echo "※ Anthropic APIキーが同梱されています。試用が終わったら削除し、キーの失効・再発行をおすすめします。"
if [ -t 0 ]; then
  read "?Enterキーで閉じます..."
fi
