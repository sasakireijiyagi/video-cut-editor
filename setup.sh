#!/bin/bash
# Video Cut Editor — セットアップスクリプト
# 実行方法: bash setup.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "========================================"
echo "  Video Cut Editor セットアップ"
echo "========================================"
echo ""

# ── 1. Homebrew ───────────────────────────────────────────────────
echo "[1/5] Homebrew を確認中..."
if command -v brew &>/dev/null; then
    BREW=$(command -v brew)
    echo "  ✓ Homebrew: $BREW"
else
    echo "  Homebrew が見つかりません。インストールします..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon の場合パスを通す
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    BREW=$(command -v brew)
    echo "  ✓ Homebrew インストール完了: $BREW"
fi

# ── 2. ffmpeg ─────────────────────────────────────────────────────
echo "[2/5] ffmpeg を確認中..."
if $BREW list ffmpeg &>/dev/null 2>&1; then
    echo "  ✓ ffmpeg: $(command -v ffmpeg)"
else
    echo "  ffmpeg をインストールします..."
    $BREW install ffmpeg
    echo "  ✓ ffmpeg インストール完了"
fi

# ── 3. conda ──────────────────────────────────────────────────────
echo "[3/5] conda を確認中..."
CONDA_BIN=""
for base in /opt/anaconda3 /opt/miniconda3 \
            "$HOME/anaconda3" "$HOME/miniconda3" \
            "$HOME/miniforge3" "$HOME/mambaforge"; do
    if [ -f "$base/bin/conda" ]; then
        CONDA_BIN="$base/bin/conda"
        CONDA_BASE="$base"
        break
    fi
done

if [ -z "$CONDA_BIN" ]; then
    echo ""
    echo "  ⚠️  Anaconda / Miniconda が見つかりませんでした。"
    echo ""
    echo "  以下からインストールしてください:"
    echo "  https://www.anaconda.com/download"
    echo ""
    echo "  インストール後、このスクリプトを再実行してください。"
    exit 1
fi
echo "  ✓ conda: $CONDA_BIN"

# ── 4. whisper ────────────────────────────────────────────────────
echo "[4/5] whisper を確認中..."
WHISPER_BIN=""

# PATH から探す
if command -v whisper &>/dev/null; then
    WHISPER_BIN=$(command -v whisper)
fi

# conda 環境から探す
if [ -z "$WHISPER_BIN" ]; then
    WHISPER_BIN=$(find "$CONDA_BASE/envs" -name "whisper" -path "*/bin/whisper" 2>/dev/null | head -1)
fi

# ベース環境から探す
if [ -z "$WHISPER_BIN" ] && [ -f "$CONDA_BASE/bin/whisper" ]; then
    WHISPER_BIN="$CONDA_BASE/bin/whisper"
fi

if [ -z "$WHISPER_BIN" ]; then
    echo "  whisper が見つかりません。新しい conda 環境にインストールします..."
    $CONDA_BIN create -n whisper_env python=3.11 -y
    "$CONDA_BASE/envs/whisper_env/bin/pip" install openai-whisper
    WHISPER_BIN="$CONDA_BASE/envs/whisper_env/bin/whisper"
    echo "  ✓ whisper インストール完了: $WHISPER_BIN"
else
    echo "  ✓ whisper: $WHISPER_BIN"
fi

# ── 5. Python + PyQt6 ────────────────────────────────────────────
echo "[5/5] Python + PyQt6 を確認中..."
PYTHON_BIN=""

for py in \
    "$CONDA_BASE/bin/python3" \
    /opt/anaconda3/bin/python3 \
    /opt/miniconda3/bin/python3 \
    "$HOME/anaconda3/bin/python3" \
    "$HOME/miniconda3/bin/python3" \
    "$HOME/miniforge3/bin/python3" \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3; do
    if [ -f "$py" ] && "$py" -c "from PyQt6.QtMultimedia import QMediaPlayer" 2>/dev/null; then
        PYTHON_BIN="$py"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "  PyQt6 が見つかりません。インストールします..."
    "$CONDA_BASE/bin/pip" install PyQt6
    PYTHON_BIN="$CONDA_BASE/bin/python3"
    echo "  ✓ PyQt6 インストール完了"
fi
echo "  ✓ Python: $PYTHON_BIN"

# ── run.sh を生成 ─────────────────────────────────────────────────
cat > "$SCRIPT_DIR/run.sh" << RUNSCRIPT
#!/bin/bash
export PATH="/usr/local/bin:/opt/homebrew/bin:\$PATH"
exec "$PYTHON_BIN" "$SCRIPT_DIR/editor.py" "\$@"
RUNSCRIPT
chmod +x "$SCRIPT_DIR/run.sh"

# ── VideoCutEditor.app を生成 ─────────────────────────────────────
APP_PATH="$SCRIPT_DIR/VideoCutEditor.app"
RUN_SH="$SCRIPT_DIR/run.sh"

osacompile -o "$APP_PATH" - << APPLESCRIPT
do shell script "$RUN_SH > /dev/null 2>&1 &"
APPLESCRIPT

# ── アイコンを設定 ────────────────────────────────────────────────
ICON_SRC="$SCRIPT_DIR/AppIcon.icns"
if [ -f "$ICON_SRC" ]; then
    mkdir -p "$APP_PATH/Contents/Resources"
    cp "$ICON_SRC" "$APP_PATH/Contents/Resources/AppIcon.icns"
    cat > "$APP_PATH/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleName</key>
    <string>Video Cut Editor</string>
    <key>CFBundleDisplayName</key>
    <string>Video Cut Editor</string>
</dict>
</plist>
PLIST
    # Finderキャッシュをリフレッシュ
    touch "$APP_PATH"
    /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH" 2>/dev/null || true
    echo "✓ アイコン設定完了"
fi

echo ""
echo "========================================"
echo "  セットアップ完了！"
echo "========================================"
echo ""
echo "  起動方法:"
echo "  $APP_PATH"
echo "  をダブルクリックしてください。"
echo ""
echo "  または: open \"$APP_PATH\""
echo ""
