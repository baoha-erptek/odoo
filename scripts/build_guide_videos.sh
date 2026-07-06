#!/usr/bin/env bash
# Build the 2 video user guides (dropship + MTO) from the Playwright
# recording specs in tests/e2e/tests/guide_flow_*.spec.ts.
#
# Usage:
#   bash scripts/build_guide_videos.sh              # record ALL chapters + build MP4s
#   bash scripts/build_guide_videos.sh concat-only  # skip recording, rebuild MP4s from chapters/
#
# Chapters land in docs/owner/videos/chapters/<flow>-<NN>.webm; a failed
# chapter can be retaken alone:
#   cd tests/e2e && GUIDE_RECORDING=1 npx playwright test guide_flow_dropship.spec.ts --grep "chuong-03"
# then re-run this script with `concat-only`.
#
# LIVE side effects per full run: 2 Etsy DRAFT listings (owner deletes from
# Shop Manager) + 1 Gearment DRAFT order (owner discards; ref in MANIFEST).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
E2E_DIR="$REPO_ROOT/tests/e2e"
OUT_DIR="$REPO_ROOT/docs/owner/videos"
CHAP_DIR="$OUT_DIR/chapters"
MODE="${1:-full}"

mkdir -p "$CHAP_DIR"

record_flow() { # $1 = dropship|mto
  local flow="$1" spec="guide_flow_$1.spec.ts" n=0
  # Fresh state per full run: chapters re-create their fixtures.
  rm -f "$E2E_DIR/.guide-state.json"
  for chapter in 01 02 03 04 05 06 07; do
    grep -q "chuong-$chapter" "$E2E_DIR/tests/$spec" || continue
    n=$((n + 1))
    echo "=== [$flow] recording chuong-$chapter ==="
    (cd "$E2E_DIR" && GUIDE_RECORDING=1 npx playwright test "$spec" --grep "chuong-$chapter")
    local webm
    webm=$(find "$E2E_DIR/artifacts" -name video.webm | head -1)
    [ -n "$webm" ] || { echo "no video for $flow chuong-$chapter"; exit 1; }
    cp "$webm" "$CHAP_DIR/$flow-$chapter.webm"
  done
}

build_mp4() { # $1 = dropship|mto
  local flow="$1" list
  list=$(mktemp)
  for f in "$CHAP_DIR/$flow"-0*.webm; do
    # Off-camera fixture RPCs run before the first goto → trim the white lead
    # (first second whose mean luma drops below 232 = content start).
    local lead inp
    # awk's early exit SIGPIPEs ffprobe — mask it (pipefail is on).
    lead=$(ffprobe -v error -f lavfi -i "movie=$f,fps=1,signalstats" \
      -show_entries frame_tags=lavfi.signalstats.YAVG -of csv=p=0 2>/dev/null \
      | awk '$1<232{print NR-1; exit}' || true)
    inp=$(python3 -c "print(max(0, ${lead:-0} - 0.5))")
    printf "file '%s'\ninpoint %s\n" "$f" "$inp" >> "$list"
  done
  ffmpeg -y -v error -f concat -safe 0 -i "$list" \
    -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p -movflags +faststart \
    "$OUT_DIR/huong_dan_$flow.mp4"
  rm -f "$list"
}

if [ "$MODE" != "concat-only" ]; then
  record_flow dropship
  record_flow mto
fi
build_mp4 dropship
build_mp4 mto

{
  echo "# Video user guides — build manifest ($(date -u +%Y-%m-%dT%H:%MZ))"
  for v in "$OUT_DIR"/huong_dan_*.mp4; do
    ffprobe -v error -show_entries format=duration,size -of csv=p=0 "$v" \
      | awk -F, -v n="$(basename "$v")" '{printf "%s  %.0fs  %.1fMB\n", n, $1, $2/1048576}'
  done
  if [ -f "$E2E_DIR/.guide-state.json" ]; then
    echo "--- run refs (cleanup targets)"
    python3 -c "import json;d=json.load(open('$E2E_DIR/.guide-state.json'));[print(f'{k}: {v}') for k,v in d.items()]"
  fi
} > "$OUT_DIR/MANIFEST.txt"
cat "$OUT_DIR/MANIFEST.txt"
