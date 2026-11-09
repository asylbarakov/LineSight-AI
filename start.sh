#!/bin/sh
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -n "${LINESIGHT_PYTHON:-}" ]; then
  "$LINESIGHT_PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo 'Python 3.10+ is required.' >&2; exit 1; }
  exec "$LINESIGHT_PYTHON" -B "$task_root/scripts/linesight.py" "$@"
fi
for task_python in python3 python; do
  if command -v "$task_python" >/dev/null 2>&1 && "$task_python" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    exec "$task_python" -B "$task_root/scripts/linesight.py" "$@"
  fi
done
echo 'Python 3.10+ is required. Install it or set LINESIGHT_PYTHON to its executable.' >&2
exit 1
