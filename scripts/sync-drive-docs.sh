#!/usr/bin/env bash
# Re-download the Nxance Google Drive folders into ../drive-sources (outside the repo).
# Re-sort into docs/ by hand afterwards if file names changed.
set -euo pipefail
DEST="$(cd "$(dirname "$0")/../.." && pwd)/drive-sources"
command -v gdown >/dev/null || { echo "Install gdown first: pip3 install gdown"; exit 1; }
mkdir -p "$DEST" && cd "$DEST"
gdown --folder "https://drive.google.com/drive/folders/1s1aaN7FbC9WdT_rTEFeyqOgKOAS2kJgi"
gdown --folder "https://drive.google.com/drive/folders/1ahS2JphdVRumHZuPzjMo2Dp_f0YhC7WK"
echo "Downloaded to $DEST"
