#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-${PROJECT_ROOT}/../EH-LLM/.venv/bin/python}"
PROMPT_FILE="${PROMPT_FILE:-${PROJECT_ROOT}/pipelines/download/filtering/filter_04_prompt.txt}"
INPUT_FILE="${INPUT_FILE:-${PROJECT_ROOT}/data_registry/papers_stage03.jsonl}"
OUTPUT_FILE="${OUTPUT_FILE:-${PROJECT_ROOT}/data_registry/papers_stage04_core_corpus.jsonl}"
PROGRESS_FILE="${PROGRESS_FILE:-${PROJECT_ROOT}/data_registry/papers_stage04_core_corpus.progress.json}"
LOG_FILE="${LOG_FILE:-${PROJECT_ROOT}/runs/stage4_local.log}"
ENV_FILE="${ENV_FILE:-${PROJECT_ROOT}/pipelines/download/.env}"
FALLBACK_ENV_FILE="${FALLBACK_ENV_FILE:-${PROJECT_ROOT}/../EH-LLM/pipelines/download/.env}"

RESET=0

usage() {
  cat <<'EOF'
Usage:
  scripts/run_local_stage4.sh [--reset]

Options:
  --reset     Remove existing stage4 output/progress before starting.
  -h, --help  Show this help text.

Environment overrides:
  PYTHON_BIN
  PROMPT_FILE
  INPUT_FILE
  OUTPUT_FILE
  PROGRESS_FILE
  LOG_FILE
  ENV_FILE
  FALLBACK_ENV_FILE
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset)
      RESET=1
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

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python not found or not executable: ${PYTHON_BIN}" >&2
  exit 1
fi

mkdir -p "$(dirname "${LOG_FILE}")"

if [[ "${RESET}" -eq 1 ]]; then
  rm -f "${OUTPUT_FILE}" "${PROGRESS_FILE}"
fi

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
elif [[ -f "${FALLBACK_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${FALLBACK_ENV_FILE}"
  set +a
fi

echo "Running local stage4"
echo "  Python:   ${PYTHON_BIN}"
echo "  Input:    ${INPUT_FILE}"
echo "  Output:   ${OUTPUT_FILE}"
echo "  Progress: ${PROGRESS_FILE}"
echo "  Prompt:   ${PROMPT_FILE}"
echo "  Log:      ${LOG_FILE}"
echo "  Env:      ${ENV_FILE} (fallback: ${FALLBACK_ENV_FILE})"

"${PYTHON_BIN}" -u "${PROJECT_ROOT}/pipelines/download/filtering/filter_04_llm_score.py" \
  --input "${INPUT_FILE}" \
  --output "${OUTPUT_FILE}" \
  --prompt-file "${PROMPT_FILE}" 2>&1 | tee "${LOG_FILE}"
