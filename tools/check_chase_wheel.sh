#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cd "$root"
python - "$tmp/expected.json" <<'PY'
import json,sys
from provlab.chase import analyze
json.dump([{'input':c['input'],'report':analyze(c['input'])}for c in json.load(open('docs/chase-controls.json'))],open(sys.argv[1],'w'))
PY
python -m pip wheel --no-deps --wheel-dir "$tmp/wheels" "$root"
python -m venv "$tmp/venv"
"$tmp/venv/bin/python" -m pip install --no-deps "$tmp"/wheels/*.whl
cd "$tmp"
"$tmp/venv/bin/python" "$root/tools/verify_chase_installed.py" "$tmp/expected.json"
