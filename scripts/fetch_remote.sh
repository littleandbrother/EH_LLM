#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_ENV_FILE="${PROJECT_ROOT}/.remote.env"

REMOTE_HOST="${EHLLM_REMOTE_HOST:-}"
REMOTE_DIR="${EHLLM_REMOTE_DIR:-}"
REMOTE_PORT="${EHLLM_REMOTE_PORT:-}"
LOCAL_DIR="${EHLLM_LOCAL_DIR:-${PROJECT_ROOT}}"
ENV_FILE="${EHLLM_REMOTE_ENV_FILE:-${DEFAULT_ENV_FILE}}"

DO_DELETE=0
DRY_RUN=0
HOST_SET=0
DIR_SET=0
PORT_SET=0
LOCAL_DIR_SET=0

FETCH_PATHS=()

DEFAULT_FETCH_PATHS=(
  "runs"
  "artifacts/reports"
  "normalized_docs"
  "provenance_docs"
  "data_registry/extracted"
)

usage() {
  cat <<'EOF'
Usage:
  scripts/fetch_remote.sh --host user@server --remote-dir /path/EH-LLM [options]

Options:
  --host HOST               Remote SSH target. Can also come from EHLLM_REMOTE_HOST.
  --remote-dir DIR          Remote project directory. Can also come from EHLLM_REMOTE_DIR.
  --port PORT               Remote SSH port. Can also come from EHLLM_REMOTE_PORT.
  --local-dir DIR           Local destination root. Default: current EH-LLM repo.
  --env-file PATH           Optional local config file to source before parsing args.
  --path RELPATH            Relative path to fetch from the remote repo. Repeatable.
  --delete                  Delete local files that no longer exist remotely for fetched paths.
  --dry-run                 Show rsync actions without changing local files.
  -h, --help                Show this help text.

Notes:
  - If no --path is given, the script fetches a default result set:
    runs, artifacts/reports, normalized_docs, provenance_docs, data_registry/extracted
  - Paths are always interpreted relative to the remote repo root.
EOF
}

load_env_file() {
  local file_path="$1"
  if [[ -f "${file_path}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${file_path}"
    set +a
  fi
}

apply_loaded_env_defaults() {
  if [[ "${HOST_SET}" -eq 0 ]]; then
    REMOTE_HOST="${EHLLM_REMOTE_HOST:-${REMOTE_HOST}}"
  fi
  if [[ "${DIR_SET}" -eq 0 ]]; then
    REMOTE_DIR="${EHLLM_REMOTE_DIR:-${REMOTE_DIR}}"
  fi
  if [[ "${PORT_SET}" -eq 0 ]]; then
    REMOTE_PORT="${EHLLM_REMOTE_PORT:-${REMOTE_PORT}}"
  fi
  if [[ "${LOCAL_DIR_SET}" -eq 0 ]]; then
    LOCAL_DIR="${EHLLM_LOCAL_DIR:-${LOCAL_DIR}}"
  fi
}

ensure_value() {
  local name="$1"
  local value="$2"
  if [[ -z "${value}" ]]; then
    echo "Missing required ${name}." >&2
    usage >&2
    exit 1
  fi
}

remote_exists() {
  local remote_path="$1"
  "${SSH_CMD[@]}" "${REMOTE_HOST}" "test -e $(printf '%q' "${remote_path}")"
}

fetch_path() {
  local relative_path="$1"
  local remote_path="${REMOTE_DIR}/${relative_path}"
  local local_path="${LOCAL_DIR}/${relative_path}"
  local rsync_opts=("-azP")

  if [[ "${DO_DELETE}" -eq 1 ]]; then
    rsync_opts+=("--delete")
  fi
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    rsync_opts+=("--dry-run")
  fi
  if [[ -n "${REMOTE_PORT}" ]]; then
    rsync_opts+=("-e" "${SSH_CMD[*]}")
  fi

  if ! remote_exists "${remote_path}"; then
    echo "Skip missing remote path: ${relative_path}" >&2
    return
  fi

  if "${SSH_CMD[@]}" "${REMOTE_HOST}" "test -d $(printf '%q' "${remote_path}")"; then
    mkdir -p "${local_path}"
    rsync "${rsync_opts[@]}" "${REMOTE_HOST}:${remote_path}/" "${local_path}/"
  else
    mkdir -p "$(dirname "${local_path}")"
    rsync "${rsync_opts[@]}" "${REMOTE_HOST}:${remote_path}" "${local_path}"
  fi
}

load_env_file "${ENV_FILE}"
apply_loaded_env_defaults

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      REMOTE_HOST="$2"
      HOST_SET=1
      shift 2
      ;;
    --remote-dir)
      REMOTE_DIR="$2"
      DIR_SET=1
      shift 2
      ;;
    --port)
      REMOTE_PORT="$2"
      PORT_SET=1
      shift 2
      ;;
    --local-dir)
      LOCAL_DIR="$2"
      LOCAL_DIR_SET=1
      shift 2
      ;;
    --env-file)
      ENV_FILE="$2"
      load_env_file "${ENV_FILE}"
      apply_loaded_env_defaults
      shift 2
      ;;
    --path)
      FETCH_PATHS+=("$2")
      shift 2
      ;;
    --delete)
      DO_DELETE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

ensure_value "--host" "${REMOTE_HOST}"
ensure_value "--remote-dir" "${REMOTE_DIR}"

SSH_CMD=("ssh")
if [[ -n "${REMOTE_PORT}" ]]; then
  SSH_CMD+=("-p" "${REMOTE_PORT}")
fi

if [[ ${#FETCH_PATHS[@]} -eq 0 ]]; then
  FETCH_PATHS=("${DEFAULT_FETCH_PATHS[@]}")
fi

echo "Fetching remote results ${REMOTE_HOST}:${REMOTE_DIR} -> ${LOCAL_DIR}"

for relative_path in "${FETCH_PATHS[@]}"; do
  echo "Fetching: ${relative_path}"
  fetch_path "${relative_path}"
done

echo
echo "Remote fetch complete."
