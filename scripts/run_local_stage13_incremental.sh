#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-${PROJECT_ROOT}/../EH-LLM/.venv/bin/python}"
CONFIG_PATH="${CONFIG_PATH:-${PROJECT_ROOT}/pipelines/download/search_config_vehbench_pass02.yaml}"
BACKFILL_MODE="${BACKFILL_MODE:-all}"
SNAPSHOT_DIR="${PROJECT_ROOT}/data_registry/local_stage13_incremental_snapshot"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python not found or not executable: ${PYTHON_BIN}" >&2
  exit 1
fi

mkdir -p "${SNAPSHOT_DIR}"

snapshot_if_exists() {
  local relpath="$1"
  local src="${PROJECT_ROOT}/${relpath}"
  if [[ -f "${src}" ]]; then
    cp "${src}" "${SNAPSHOT_DIR}/$(basename "${relpath}")"
  fi
}

echo "Using python: ${PYTHON_BIN}"
echo "Using config: ${CONFIG_PATH}"
echo "Backfill mode: ${BACKFILL_MODE}"
echo "Snapshot dir: ${SNAPSHOT_DIR}"

snapshot_if_exists "data_registry/papers.jsonl"
snapshot_if_exists "data_registry/papers_stage01.jsonl"
snapshot_if_exists "data_registry/papers_stage02.jsonl"
snapshot_if_exists "data_registry/papers_stage03.jsonl"
snapshot_if_exists "data_registry/papers_stage04_core_corpus.jsonl"

rm -f \
  "${PROJECT_ROOT}/data_registry/papers_stage01.jsonl" \
  "${PROJECT_ROOT}/data_registry/papers_stage02.jsonl" \
  "${PROJECT_ROOT}/data_registry/papers_stage03.jsonl"

"${PYTHON_BIN}" "${PROJECT_ROOT}/pipelines/download/search_papers.py" \
  --config "${CONFIG_PATH}" \
  --skip-pdf

case "${BACKFILL_MODE}" in
  none)
    echo "Skipping abstract backfill."
    ;;
  oa)
    "${PYTHON_BIN}" "${PROJECT_ROOT}/pipelines/download/backfill_abstracts.py" --source oa
    ;;
  s2)
    "${PYTHON_BIN}" "${PROJECT_ROOT}/pipelines/download/backfill_abstracts.py" --source s2
    ;;
  all)
    "${PYTHON_BIN}" "${PROJECT_ROOT}/pipelines/download/backfill_abstracts.py"
    ;;
  *)
    echo "Unsupported BACKFILL_MODE: ${BACKFILL_MODE}" >&2
    exit 1
    ;;
esac

"${PYTHON_BIN}" "${PROJECT_ROOT}/pipelines/download/filtering/filter_01_topic.py"
"${PYTHON_BIN}" "${PROJECT_ROOT}/pipelines/download/filtering/filter_02_experiment.py"
"${PYTHON_BIN}" "${PROJECT_ROOT}/pipelines/download/filtering/filter_03_quantitative.py"

echo
echo "Incremental local stage1-3 run complete."
for relpath in \
  "data_registry/papers.jsonl" \
  "data_registry/papers_stage01.jsonl" \
  "data_registry/papers_stage02.jsonl" \
  "data_registry/papers_stage03.jsonl"; do
  file_path="${PROJECT_ROOT}/${relpath}"
  if [[ -f "${file_path}" ]]; then
    printf "  %-36s %s lines\n" "${relpath}" "$(wc -l < "${file_path}")"
  fi
done
