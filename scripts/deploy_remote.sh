#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_ENV_FILE="${PROJECT_ROOT}/.remote.env"

REMOTE_HOST="${EHLLM_REMOTE_HOST:-}"
REMOTE_DIR="${EHLLM_REMOTE_DIR:-}"
REMOTE_PORT="${EHLLM_REMOTE_PORT:-}"
ENV_FILE="${EHLLM_REMOTE_ENV_FILE:-${DEFAULT_ENV_FILE}}"

WITH_ENV=0
DO_DELETE=0
DRY_RUN=0
HOST_SET=0
DIR_SET=0
PORT_SET=0

SYNC_PATHS=()
EXTRA_EXCLUDES=()

DEFAULT_EXCLUDES=(
  ".git/"
  ".venv/"
  "__pycache__/"
  ".pytest_cache/"
  "*.pyc"
  ".DS_Store"
  ".remote*.env"
  "artifacts/checkpoints/"
  "runs/"
  "data_registry/raw/"
  "data_registry/parsed/"
  "data_registry/extracted/"
  "parsed_docs/"
  "normalized_docs/"
  "provenance_docs/"
)

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy_remote.sh --host user@server --remote-dir /path/EH-LLM [options]

Options:
  --host HOST               Remote SSH target. Can also come from EHLLM_REMOTE_HOST.
  --remote-dir DIR          Remote project directory. Can also come from EHLLM_REMOTE_DIR.
  --port PORT               Remote SSH port. Can also come from EHLLM_REMOTE_PORT.
  --env-file PATH           Optional local config file to source before parsing args.
  --sync-path RELPATH       Extra relative path to rsync after the code sync. Repeatable.
  --with-env                Also sync pipelines/download/.env after the code sync.
  --exclude PATTERN         Extra rsync exclude pattern. Repeatable.
  --delete                  Delete remote files that no longer exist locally for the main code sync.
  --dry-run                 Show rsync/ssh actions without changing the remote host.
  -h, --help                Show this help text.

Notes:
  - The main code sync excludes large/generated directories by default.
  - Use --sync-path data_registry/raw to send local PDFs when needed.
  - A local .remote.env file can define EHLLM_REMOTE_HOST and EHLLM_REMOTE_DIR.
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

rsync_path() {
  local local_path="$1"
  local remote_path="$2"
  local path_opts=("-azP")
  local ssh_cmd=("ssh")

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    path_opts+=("--dry-run")
  fi
  if [[ -n "${REMOTE_PORT}" ]]; then
    ssh_cmd+=("-p" "${REMOTE_PORT}")
  fi
  path_opts+=("-e" "${ssh_cmd[*]}")

  if [[ -d "${local_path}" ]]; then
    "${ssh_cmd[@]}" "${REMOTE_HOST}" "mkdir -p $(printf '%q' "${remote_path}")"
    rsync "${path_opts[@]}" "${local_path}/" "${REMOTE_HOST}:${remote_path}/"
  else
    "${ssh_cmd[@]}" "${REMOTE_HOST}" "mkdir -p $(printf '%q' "$(dirname "${remote_path}")")"
    rsync "${path_opts[@]}" "${local_path}" "${REMOTE_HOST}:${remote_path}"
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
    --env-file)
      ENV_FILE="$2"
      load_env_file "${ENV_FILE}"
      apply_loaded_env_defaults
      shift 2
      ;;
    --sync-path)
      SYNC_PATHS+=("$2")
      shift 2
      ;;
    --with-env)
      WITH_ENV=1
      shift
      ;;
    --exclude)
      EXTRA_EXCLUDES+=("$2")
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

if [[ "${WITH_ENV}" -eq 1 ]]; then
  SYNC_PATHS+=("pipelines/download/.env")
fi

RSYNC_OPTS=("-azP")
SSH_CMD=("ssh")
if [[ -n "${REMOTE_PORT}" ]]; then
  SSH_CMD+=("-p" "${REMOTE_PORT}")
  RSYNC_OPTS+=("-e" "${SSH_CMD[*]}")
fi
if [[ "${DO_DELETE}" -eq 1 ]]; then
  RSYNC_OPTS+=("--delete")
fi
if [[ "${DRY_RUN}" -eq 1 ]]; then
  RSYNC_OPTS+=("--dry-run")
fi

for pattern in "${DEFAULT_EXCLUDES[@]}"; do
  RSYNC_OPTS+=("--exclude=${pattern}")
done
if ((${#EXTRA_EXCLUDES[@]} > 0)); then
  for pattern in "${EXTRA_EXCLUDES[@]}"; do
    RSYNC_OPTS+=("--exclude=${pattern}")
  done
fi

echo "Deploying ${PROJECT_ROOT} -> ${REMOTE_HOST}:${REMOTE_DIR}"
if [[ "${DRY_RUN}" -eq 0 ]]; then
  "${SSH_CMD[@]}" "${REMOTE_HOST}" "mkdir -p $(printf '%q' "${REMOTE_DIR}")"
else
  echo "[dry-run] ${SSH_CMD[*]} ${REMOTE_HOST} mkdir -p ${REMOTE_DIR}"
fi

rsync "${RSYNC_OPTS[@]}" "${PROJECT_ROOT}/" "${REMOTE_HOST}:${REMOTE_DIR}/"

if ((${#SYNC_PATHS[@]} > 0)); then
  for relative_path in "${SYNC_PATHS[@]}"; do
    local_path="${PROJECT_ROOT}/${relative_path}"
    remote_path="${REMOTE_DIR}/${relative_path}"

    if [[ ! -e "${local_path}" ]]; then
      echo "Skip missing path: ${relative_path}" >&2
      continue
    fi

    echo "Syncing extra path: ${relative_path}"
    rsync_path "${local_path}" "${remote_path}"
  done
fi

echo
echo "Remote deploy complete."
echo "Next step:"
echo "  ${PROJECT_ROOT}/scripts/run_remote.sh --host ${REMOTE_HOST} --remote-dir ${REMOTE_DIR}${REMOTE_PORT:+ --port ${REMOTE_PORT}} --command '<your command>'"
