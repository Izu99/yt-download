#!/usr/bin/env bash
# YouTube MP3 Downloader installer for Linux Mint / Cinnamon.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$HOME/.local/bin"
BIN="$BIN_DIR/yt-mp3"
APP_DIR="$HOME/.local/share/applications"
VENV="$HERE/.venv"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }

# ---- dependencies -----------------------------------------------------------
say "Checking dependencies"
MISSING=()
python3 -c "import tkinter" 2>/dev/null || MISSING+=(python3-tk)
python3 -c "import venv"    2>/dev/null || MISSING+=(python3-venv)
command -v ffmpeg >/dev/null || MISSING+=(ffmpeg)

if [ ${#MISSING[@]} -gt 0 ]; then
    warn "Missing packages: ${MISSING[*]}"
    say "Installing (sudo required)…"
    sudo apt-get install -y "${MISSING[@]}"
else
    say "All dependencies present"
fi

# ---- virtualenv -------------------------------------------------------------
# yt-dlp lives in the venv rather than apt: the packaged version goes stale fast
# and YouTube breaks old extractors.
if [ ! -x "$VENV/bin/python" ]; then
    say "Creating virtualenv → $VENV"
    python3 -m venv "$VENV"
fi

say "Installing Python packages (customtkinter, yt-dlp)"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet --upgrade customtkinter yt-dlp

# ---- link the launcher ------------------------------------------------------
say "Linking launcher → $BIN"
mkdir -p "$BIN_DIR"
chmod +x "$HERE/run.sh"
ln -sf "$HERE/run.sh" "$BIN"

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) warn "$BIN_DIR is not on your PATH — add it to ~/.bashrc:"
       printf '    export PATH="$HOME/.local/bin:$PATH"\n' ;;
esac

# ---- menu entry -------------------------------------------------------------
say "Adding menu entry"
mkdir -p "$APP_DIR"
cat > "$APP_DIR/yt-mp3.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=YouTube MP3 Downloader
Comment=Download YouTube audio as MP3
Exec=$BIN
Icon=multimedia-audio-player
Terminal=false
Categories=AudioVideo;Audio;
EOF

update-desktop-database "$APP_DIR" 2>/dev/null || true

say "Installed. Launch from the menu, or run: yt-mp3"
