#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_ENV_FILE="${PROJECT_ROOT}/.remote.env"

REMOTE_HOST="${EHLLM_REMOTE_HOST:-}"
REMOTE_DIR="${EHLLM_REMOTE_DIR:-}"
REMOTE_PORT="${EHLLM_REMOTE_PORT:-}"
REMOTE_SESSION="${EHLLM_REMOTE_SESSION:-ehllm}"
REMOTE_VENV="${EHLLM_REMOTE_VENV:-.venv}"
ENV_FILE="${EHLLM_REMOTE_ENV_FILE:-${DEFAULT_ENV_FILE}}"
DEFAULT_REQUIREMENTS_FILE="pipelines/download/requirements.txt"
REQUIREMENTS_FILES=()

COMMAND=""
BOOTSTRAP=0
RESTART=0
HOST_SET=0
DIR_SET=0
PORT_SET=0
SESSION_SET=0
VENV_SET=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_remote.sh --host user@server --remote-dir /path/EH-LLM --command "python ..."

Options:
  --host HOST               Remote SSH target. Can also come from EHLLM_REMOTE_HOST.
  --remote-dir DIR          Remote project directory. Can also come from EHLLM_REMOTE_DIR.
  --port PORT               Remote SSH port. Can also come from EHLLM_REMOTE_PORT.
  --command CMD             Command to execute on the remote host inside tmux.
  --session NAME            tmux session name. Default: ehllm or EHLLM_REMOTE_SESSION.
  --venv DIR                Remote virtualenv directory relative to the repo. Default: .venv.
  --bootstrap               Create the remote virtualenv if missing and install requirements.
  --requirements PATH       Requirements file used with --bootstrap. Repeatable.
  --restart                 Replace an existing tmux session with the same name.
  --env-file PATH           Optional local config file to source before parsing args.
  -h, --help                Show this help text.

Notes:
  - The command runs as: cd <remote-dir> && source <venv>/bin/activate && <command>
  - After launch, attach with: ssh <host> 'tmux attach -t <session>'
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
  if [[ "${SESSION_SET}" -eq 0 ]]; then
    REMOTE_SESSION="${EHLLM_REMOTE_SESSION:-${REMOTE_SESSION}}"
  fi
  if [[ "${VENV_SET}" -eq 0 ]]; then
    REMOTE_VENV="${EHLLM_REMOTE_VENV:-${REMOTE_VENV}}"
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

append_requirement_file() {
  local file_path="$1"
  REQUIREMENTS_FILES+=("${file_path}")
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
    --command)
      COMMAND="$2"
      shift 2
      ;;
    --session)
      REMOTE_SESSION="$2"
      SESSION_SET=1
      shift 2
      ;;
    --venv)
      REMOTE_VENV="$2"
      VENV_SET=1
      shift 2
      ;;
    --bootstrap)
      BOOTSTRAP=1
      shift
      ;;
    --requirements)
      append_requirement_file "$2"
      shift 2
      ;;
    --restart)
      RESTART=1
      shift
      ;;
    --env-file)
      ENV_FILE="$2"
      load_env_file "${ENV_FILE}"
      apply_loaded_env_defaults
      shift 2
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
ensure_value "--command" "${COMMAND}"

if ((${#REQUIREMENTS_FILES[@]} == 0)); then
  append_requirement_file "${DEFAULT_REQUIREMENTS_FILE}"
fi

SSH_CMD=("ssh")
if [[ -n "${REMOTE_PORT}" ]]; then
  SSH_CMD+=("-p" "${REMOTE_PORT}")
fi

REMOTE_DIR_Q="$(printf '%q' "${REMOTE_DIR}")"
REMOTE_SESSION_Q="$(printf '%q' "${REMOTE_SESSION}")"
REMOTE_VENV_Q="$(printf '%q' "${REMOTE_VENV}")"
BOOTSTRAP_CMD=""
if [[ "${BOOTSTRAP}" -eq 1 ]]; then
  BOOTSTRAP_CMD="mkdir -p ${REMOTE_DIR_Q} && cd ${REMOTE_DIR_Q} && "
  BOOTSTRAP_CMD+="if [[ ! -d ${REMOTE_VENV_Q} ]]; then python3 -m venv ${REMOTE_VENV_Q}; fi && "
  BOOTSTRAP_CMD+="source ${REMOTE_VENV_Q}/bin/activate && "
  BOOTSTRAP_CMD+="python -m pip install --upgrade pip setuptools wheel"
  for requirements_file in "${REQUIREMENTS_FILES[@]}"; do
    requirements_file_q="$(printf '%q' "${requirements_file}")"
    BOOTSTRAP_CMD+=" && python -m pip install -r ${requirements_file_q}"
  done
fi

JOB_CMD="cd ${REMOTE_DIR_Q} && source ${REMOTE_VENV_Q}/bin/activate && ${COMMAND}"
JOB_CMD_Q="$(printf '%q' "${JOB_CMD}")"

SESSION_EXISTS_CHECK="tmux has-session -t ${REMOTE_SESSION_Q} 2>/dev/null"
if [[ "${RESTART}" -eq 1 ]]; then
  SESSION_PREP="if ${SESSION_EXISTS_CHECK}; then tmux kill-session -t ${REMOTE_SESSION_Q}; fi"
else
  SESSION_PREP="if ${SESSION_EXISTS_CHECK}; then echo 'tmux session ${REMOTE_SESSION} already exists; use --restart to replace it.' >&2; exit 1; fi"
fi

REMOTE_SCRIPT="set -euo pipefail; "
if [[ -n "${BOOTSTRAP_CMD}" ]]; then
  REMOTE_SCRIPT+="${BOOTSTRAP_CMD}; "
fi
REMOTE_SCRIPT+="mkdir -p ${REMOTE_DIR_Q}; "
REMOTE_SCRIPT+="${SESSION_PREP}; "
REMOTE_SCRIPT+="tmux new-session -d -s ${REMOTE_SESSION_Q} bash -lc ${JOB_CMD_Q}; "
REMOTE_SCRIPT+="sleep 1; "
REMOTE_SCRIPT+="tmux capture-pane -pt ${REMOTE_SESSION_Q} | tail -n 20"

echo "Launching remote command in tmux session '${REMOTE_SESSION}'"
"${SSH_CMD[@]}" "${REMOTE_HOST}" "${REMOTE_SCRIPT}"

echo
echo "Attach with:"
echo "  ${SSH_CMD[*]} ${REMOTE_HOST} 'tmux attach -t ${REMOTE_SESSION}'"
