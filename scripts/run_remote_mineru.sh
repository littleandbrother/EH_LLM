#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.remote.exp.env"

SESSION="vehbench_mineru"
DEVICE="${MINERU_DEVICE:-cuda}"
BACKEND="${MINERU_BACKEND:-pipeline}"
SOURCE="${MINERU_SOURCE:-modelscope}"
LIMIT=""
PAPER_ID=""
BOOTSTRAP=0
FORCE=0
STATUS=0
RESTART=0
NO_DEPLOY=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_remote_mineru.sh [options]

Options:
  --env-file PATH   Remote config file. Default: .remote.exp.env
  --session NAME    tmux session name. Default: vehbench_mineru
  --device NAME     MinerU device. Default: cuda
  --backend NAME    MinerU backend. Default: pipeline
  --source NAME     MinerU model source. Default: modelscope
  --limit N         Process at most N papers
  --paper-id ID     Process one specific paper
  --force           Re-run papers even if outputs already exist
  --status          Show remote MinerU status instead of starting a batch
  --bootstrap       Create/update remote venv before launch
  --restart         Replace an existing tmux session
  --no-deploy       Skip syncing stage4 output/raw PDFs before launch
  -h, --help        Show this help text.

Notes:
  - This workflow assumes stage4 and cleanup_pdfs run locally.
  - By default it syncs:
      data_registry/papers_stage04_core_corpus.jsonl
      data_registry/raw
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --session)
      SESSION="$2"
      shift 2
      ;;
    --device)
      DEVICE="$2"
      shift 2
      ;;
    --backend)
      BACKEND="$2"
      shift 2
      ;;
    --source)
      SOURCE="$2"
      shift 2
      ;;
    --limit)
      LIMIT="$2"
      shift 2
      ;;
    --paper-id)
      PAPER_ID="$2"
      shift 2
      ;;
    --bootstrap)
      BOOTSTRAP=1
      shift
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --status)
      STATUS=1
      shift
      ;;
    --restart)
      RESTART=1
      shift
      ;;
    --no-deploy)
      NO_DEPLOY=1
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

if [[ "${NO_DEPLOY}" -eq 0 ]]; then
  "${PROJECT_ROOT}/scripts/deploy_remote.sh" \
    --env-file "${ENV_FILE}" \
    --sync-path data_registry/papers_stage04_core_corpus.jsonl \
    --sync-path data_registry/raw
fi

COMMAND=(python -u ingestion/mineru_runner.py)
if [[ "${STATUS}" -eq 1 ]]; then
  COMMAND+=(--status)
else
  COMMAND+=(--device "${DEVICE}" --backend "${BACKEND}" --source "${SOURCE}")
  if [[ -n "${LIMIT}" ]]; then
    COMMAND+=(--limit "${LIMIT}")
  fi
  if [[ -n "${PAPER_ID}" ]]; then
    COMMAND+=(--paper-id "${PAPER_ID}")
  fi
  if [[ "${FORCE}" -eq 1 ]]; then
    COMMAND+=(--force)
  fi
fi

COMMAND_STRING="mkdir -p runs && $(printf '%q ' "${COMMAND[@]}")2>&1 | tee runs/${SESSION}.log"

RUN_ARGS=(
  --env-file "${ENV_FILE}"
  --session "${SESSION}"
  --command "${COMMAND_STRING}"
)

if [[ "${BOOTSTRAP}" -eq 1 ]]; then
  RUN_ARGS+=(--bootstrap --requirements ingestion/requirements.txt)
fi
if [[ "${RESTART}" -eq 1 ]]; then
  RUN_ARGS+=(--restart)
fi

"${PROJECT_ROOT}/scripts/run_remote.sh" "${RUN_ARGS[@]}"
