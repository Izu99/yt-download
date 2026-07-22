#!/usr/bin/env bash
# Launch the YouTube MP3 Downloader using the project virtualenv.
set -euo pipefail

# readlink -f so this still works when invoked through the ~/.local/bin symlink.
DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

# Put the venv first so the app's `yt-dlp` subprocess call resolves to the
# venv copy rather than an older system-wide one.
export PATH="$DIR/.venv/bin:$PATH"

exec "$DIR/.venv/bin/python" "$DIR/yt-mp3.py" "$@"
