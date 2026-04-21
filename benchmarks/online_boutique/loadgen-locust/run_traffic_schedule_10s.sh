#!/usr/bin/env bash

set -euo pipefail

SCHEDULE_FILE="${1:-}"
WORKERS="${2:-12}"
RUN_TIME="${3:-14d}"
shift $(( $# > 3 ? 3 : $# ))

if [[ -z "$SCHEDULE_FILE" ]]; then
  echo "Usage: $0 <schedule_csv> [workers] [run_time] [locust args...]" >&2
  exit 1
fi

ROOT_DIR="${ROOT_DIR:-$(pwd)}"
PROFILE="${OB_PROFILE:-day_normal}"
SCENARIO_ID="${OB_SCENARIO_ID:-ob-traffic-schedule-10s-v1}"

# Use the minimal schedule-only locustfile by default.
export LOCUSTFILE="${LOCUSTFILE:-$ROOT_DIR/benchmarks/online_boutique/loadgen-locust/locustfile.py}"

export OB_ENABLE_DYNAMIC_SHAPE=1
export OB_DYNAMIC_SHAPE="schedule_file"
export OB_SHAPE_FILE="$(
  python - "$SCHEDULE_FILE" <<'PY'
import os
import sys
from pathlib import Path
print(str(Path(sys.argv[1]).expanduser().resolve()))
PY
)"
export OB_SHAPE_STEP_S="${OB_SHAPE_STEP_S:-10}"
export OB_SHAPE_SPAWN_RATE="${OB_SHAPE_SPAWN_RATE:-300}"

# Ensure the shape stops at RUN_TIME, even if the shell environment
# already has an old OB_SHAPE_DURATION_S exported.
export OB_SHAPE_DURATION_S="$(
  python - "$RUN_TIME" <<'PY'
import re
import sys
value = sys.argv[1].strip().lower()
match = re.fullmatch(r'(\d+)([smhd])', value)
if not match:
    # Default 14 days.
    print(14 * 86400)
    raise SystemExit(0)
amount = int(match.group(1))
unit = match.group(2)
scale = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[unit]
print(amount * scale)
PY
)"

# Make log dir deterministic per invocation (avoid inheriting old env state).
if [[ "${OB_KEEP_LOCUST_LOG_DIR:-0}" == "1" ]]; then
  : "${LOCUST_LOG_DIR:?OB_KEEP_LOCUST_LOG_DIR=1 requires LOCUST_LOG_DIR to be set}"
else
  export LOCUST_LOG_DIR="$(mktemp -d /tmp/ob-locust-schedule.XXXXXX)"
fi

export OB_PROFILE="$PROFILE"
export OB_SCENARIO_ID="$SCENARIO_ID"

"$ROOT_DIR/benchmarks/online_boutique/loadgen-locust/run_distributed.sh" \
  "$WORKERS" 1 1 "$RUN_TIME" "$@"

