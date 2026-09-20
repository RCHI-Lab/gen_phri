#!/bin/bash
# usage: render_preview.sh tNN [mode...]  (python http.server on 18931 serving scratch/preview)
REPO=$(cd "$(dirname "$0")/../../../.." && pwd)
S=${WEB_SCENE_SCRATCH:-$REPO/local-data/scene-build}
mkdir -p "$S/overlays" "$S/preview"
t=$1; shift; modes=${@:-orig json}
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for mode in $modes; do
  rm -f $S/overlays/${t}_render_$mode.png; prof=$(mktemp -d $S/preview/prof.XXXX)
  "$CH" --headless=new --user-data-dir=$prof --no-first-run --enable-unsafe-swiftshader --use-angle=swiftshader \
    --window-size=1280,720 --virtual-time-budget=120000 --screenshot=$S/overlays/${t}_render_$mode.png \
    "http://localhost:18931/index.html?t=$t&mode=$mode" >/dev/null 2>&1 &
  pid=$!
  for i in $(seq 1 150); do sleep 2; kill -0 $pid 2>/dev/null || break; [ -s $S/overlays/${t}_render_$mode.png ] && sleep 2 && break; done
  pkill -9 -f "$prof" 2>/dev/null; rm -rf $prof
done
