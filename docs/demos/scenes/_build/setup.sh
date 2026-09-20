#!/usr/bin/env bash
# Install everything needed to rebuild the demo scenes, into <repo>/local-data/scene-build.
#
#   ./setup.sh [path/to/final_tasks_50_*.tar.gz | path/to/final_tasks_export_*/]
#
# Without an argument it looks for the archive or an extracted export in <repo>/local-data.
# Nothing is installed system-wide and nothing outside local-data/ is touched.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
SCRATCH="${WEB_SCENE_SCRATCH:-$REPO/local-data/scene-build}"

for tool in python3 node npm curl tar git; do
  command -v "$tool" >/dev/null || { echo "error: $tool is required but not installed" >&2; exit 1; }
done

mkdir -p "$SCRATCH"
cd "$SCRATCH"

# 1. The generation records: 50 task folders with videos, configs, logs and the
#    human/robot state traces. Not in git (about 500 MB); supply it once.
export_dir="${1:-}"
if [ -n "$export_dir" ] && [ -d "$export_dir" ]; then
  ln -sfn "$(cd "$export_dir" && pwd)" export
elif [ -z "$export_dir" ] && [ -e export ]; then
  echo "export/ already present"
else
  archive="$export_dir"
  if [ -z "$archive" ]; then
    archive="$(ls -1 "$REPO"/local-data/final_tasks_*.tar.gz 2>/dev/null | head -1 || true)"
    extracted="$(ls -1d "$REPO"/local-data/final_tasks_export_* 2>/dev/null | head -1 || true)"
    [ -n "$extracted" ] && { ln -sfn "$extracted" export; archive=""; }
  fi
  if [ -n "$archive" ]; then
    echo "==> extracting $(basename "$archive")"
    mkdir -p export_src && tar -xzf "$archive" -C export_src
    ln -sfn "$(ls -1d "$PWD"/export_src/final_tasks_export_* | head -1)" export
  elif [ ! -e export ]; then
    echo "error: no task export found. Pass the archive or extracted folder:" >&2
    echo "       ./setup.sh /path/to/final_tasks_50_*.tar.gz" >&2
    exit 1
  fi
fi

# 2. Python: meshes, poses and simplification.
if [ ! -x venv/bin/python ]; then
  echo "==> creating venv"
  python3 -m venv venv
fi
echo "==> installing python packages"
./venv/bin/pip install --quiet --upgrade pip
./venv/bin/pip install --quiet numpy scipy trimesh mujoco fast-simplification pillow matplotlib

# 3. Node: glTF merging, optimisation and texture resizing.
echo "==> installing node packages"
mkdir -p node
cd node
[ -f package.json ] || npm init -y >/dev/null
npm install --silent --no-fund --no-audit \
  @gltf-transform/core @gltf-transform/extensions @gltf-transform/functions meshoptimizer sharp
cd ..

# 4. The Stretch robot model (Hello Robot, public repository).
if [ ! -d robot/stretch_mujoco ]; then
  echo "==> cloning stretch_mujoco"
  mkdir -p robot
  git clone --depth 1 --quiet https://github.com/hello-robot/stretch_mujoco robot/stretch_mujoco
fi

cat <<EOF

Setup complete in $SCRATCH

Rebuild every scene (downloads each SceneSmith room, ~435 MB, then deletes it):
  $SCRATCH/venv/bin/python $HERE/run_all.py

One task only:
  $SCRATCH/venv/bin/python $HERE/run_all.py --tasks t07
EOF
