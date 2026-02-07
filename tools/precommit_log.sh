#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <hook-name> <command> [args...]" >&2
  exit 2
fi

HOOK_NAME="$1"
shift
CMD=("$@")

LOG_DIR=".precommit_logs"
mkdir -p "$LOG_DIR"

ROOT_DIR=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
LOG_PATH="$LOG_DIR/${HOOK_NAME}-${STAMP}.log"
CMD_STR=$(printf '%q ' "${CMD[@]}")

(
  set +e
  echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] Hook '${HOOK_NAME}' starting"
  echo "Command: ${CMD_STR}"
  "${CMD[@]}"
  RC=$?
  echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] Hook '${HOOK_NAME}' completed with exit code ${RC}"
  exit "${RC}"
) 2>&1 | tee "${LOG_PATH}"

RC=${PIPESTATUS[0]}
if [[ ${RC} -eq 0 ]]; then
  echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] Hook '${HOOK_NAME}' succeeded" | tee -a "${LOG_PATH}"
else
  echo "[$(date -u +'%Y-%m-%d %H:%M:%S')] Hook '${HOOK_NAME}' failed with exit code ${RC}" | tee -a "${LOG_PATH}"
fi

exit "${RC}"
