from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .bootstrap import ensure_autora_core_path

ensure_autora_core_path()

from sklearn.ensemble import RandomForestRegressor

from autora.experimentalist.random import pool as random_pool
from autora.state import estimator_on_state, on_state
from autora.variable import DV, IV, ValueType, VariableCollection

from ..eval.runtime import LOG_SCALE_KEYS, build_request_from_task, load_tasks, ordered_variable_keys, score_interaction
from ..verifier.v1.calibration import load_frequency_profile
from ..verifier.v1.evaluator import evaluate_request
from .state import VehBenchState


def load_demo_task(
    tasks_file: str | Path,
    split: str = "test-ood",
    index: int = 0,
) -> dict:
    tasks = load_tasks(tasks_file, task_type="frequency_matching", split=split)
    if index >= len(tasks):
        raise IndexError(f"Requested task index {index}, but only found {len(tasks)} matching tasks")
    return tasks[index]


def _uses_log_scale(task: dict, key: str) -> bool:
    bound = (task.get("variable_bounds") or {}).get(key) or {}
    low = float(bound.get("min") or 0.0)
    high = float(bound.get("max") or 0.0)
    return key in LOG_SCALE_KEYS and low > 0 and high / max(low, 1e-12) >= 50.0


def _allowed_values(task: dict, key: str, points: int = 11) -> np.ndarray:
    bound = dict((task.get("variable_bounds") or {})[key])
    low = float(bound["min"])
    high = float(bound["max"])
    if _uses_log_scale(task, key):
        return np.geomspace(low, high, num=points)
    return np.linspace(low, high, num=points)


def task_to_variable_collection(task: dict, points_per_variable: int = 11) -> VariableCollection:
    independent_variables = []
    for key in ordered_variable_keys(task):
        bound = dict((task.get("variable_bounds") or {})[key])
        independent_variables.append(
            IV(
                name=key,
                allowed_values=_allowed_values(task, key, points=points_per_variable),
                units=str(bound.get("unit") or ""),
                type=ValueType.REAL,
            )
        )
    dependent_variables = [
        DV(name="score", units="a.u."),
        DV(name="frequency_error_pct", units="pct"),
        DV(name="resonant_frequency_hz", units="Hz"),
    ]
    return VariableCollection(
        independent_variables=independent_variables,
        dependent_variables=dependent_variables,
    )


def initialize_state(task: dict, points_per_variable: int = 11) -> VehBenchState:
    return VehBenchState(
        variables=task_to_variable_collection(task, points_per_variable=points_per_variable),
        task=task,
        experiment_data=pd.DataFrame(),
    )


def _candidate_signature(task: dict, candidate: dict) -> tuple[float, ...]:
    return tuple(round(float(candidate[name]), 9) for name in ordered_variable_keys(task))


def _seen_signatures(state: VehBenchState) -> set[tuple[float, ...]]:
    seen: set[tuple[float, ...]] = set()
    for trace in state.traces:
        candidate = trace.get("candidate") or {}
        seen.add(_candidate_signature(state.task, candidate))
    return seen


def _target_frequency(task: dict) -> float | None:
    fixed = task.get("fixed_conditions") or {}
    value = fixed.get("target_resonant_frequency_hz")
    return None if value is None else float(value)


@on_state(output=["conditions"])
def random_experimentalist(
    variables: VariableCollection,
    state: VehBenchState,
    num_samples: int = 6,
    random_state: int = 0,
) -> pd.DataFrame:
    seen = _seen_signatures(state)
    candidates = random_pool(variables, num_samples=max(num_samples * 4, num_samples), random_state=random_state, replace=True)
    rows = []
    for row in candidates.to_dict(orient="records"):
        signature = _candidate_signature(state.task, row)
        if signature in seen:
            continue
        rows.append(row)
        seen.add(signature)
        if len(rows) >= num_samples:
            break
    return pd.DataFrame(rows)


@on_state(output=["experiment_data", "traces", "cycle_summaries"])
def verifier_experiment_runner(
    state: VehBenchState,
    conditions: pd.DataFrame,
    cycle_label: str,
    apply_frequency_calibration: bool = True,
    use_task_anchors: bool = False,
) -> tuple[pd.DataFrame, list[dict], list[dict]]:
    if conditions is None or conditions.empty:
        empty = pd.DataFrame(columns=[*ordered_variable_keys(state.task), "score", "frequency_error_pct", "resonant_frequency_hz"])
        summary = {
            "cycle_label": cycle_label,
            "query_count": 0,
            "feasible_found": False,
            "best_score": None,
            "best_frequency_error_pct": None,
        }
        return empty, [], [summary]

    calibration_profile = load_frequency_profile() if apply_frequency_calibration else None
    target_frequency = _target_frequency(state.task)
    base_query_index = len(state.traces)
    experiment_rows: list[dict] = []
    traces: list[dict] = []

    for offset, candidate in enumerate(conditions.to_dict(orient="records"), start=1):
        query_index = base_query_index + offset
        candidate = {key: float(candidate[key]) for key in ordered_variable_keys(state.task)}
        request = build_request_from_task(
            state.task,
            candidate,
            candidate_id=f"{state.task['task_id']}::autora-poc::{query_index}",
        )
        interaction = evaluate_request(
            request,
            task=state.task,
            apply_frequency_calibration=apply_frequency_calibration,
            calibration_profile=calibration_profile,
            use_task_anchors=use_task_anchors,
        )
        response = interaction["response"]
        outputs = response.get("outputs") or {}
        frequency = outputs.get("resonant_frequency_hz")
        frequency_error_pct = None
        if target_frequency is not None and frequency is not None:
            frequency_error_pct = abs(float(frequency) - target_frequency) / max(abs(target_frequency), 1e-9) * 100.0
        score = score_interaction(state.task, interaction)
        row = dict(candidate)
        row.update(
            {
                "query_index": query_index,
                "cycle_label": cycle_label,
                "resonant_frequency_hz": frequency,
                "frequency_error_pct": frequency_error_pct,
                "score": score,
                "normalized_objective": response.get("normalized_objective"),
                "is_feasible": bool(response.get("is_feasible")),
                "violation_count": len(response.get("violations") or []),
            }
        )
        experiment_rows.append(row)
        traces.append(
            {
                "query_index": query_index,
                "cycle_label": cycle_label,
                "candidate": candidate,
                "score": score,
                "interaction": interaction,
            }
        )

    experiment_data = pd.DataFrame(experiment_rows)
    best_idx = experiment_data["score"].astype(float).idxmax()
    best_row = experiment_data.loc[best_idx]
    summary = {
        "cycle_label": cycle_label,
        "query_count": int(len(experiment_data)),
        "feasible_found": bool(experiment_data["is_feasible"].any()),
        "best_score": round(float(best_row["score"]), 6),
        "best_frequency_error_pct": None
        if pd.isna(best_row["frequency_error_pct"])
        else round(float(best_row["frequency_error_pct"]), 6),
    }
    return experiment_data, traces, [summary]


def make_score_theorist(random_state: int = 0):
    model = RandomForestRegressor(
        n_estimators=200,
        min_samples_leaf=2,
        random_state=random_state,
    )
    return estimator_on_state(model)


@on_state(output=["conditions"])
def surrogate_guided_experimentalist(
    state: VehBenchState,
    variables: VariableCollection,
    num_samples: int = 3,
    candidate_pool_size: int = 128,
    random_state: int = 0,
) -> pd.DataFrame:
    seen = _seen_signatures(state)
    pool = random_pool(
        variables,
        num_samples=max(candidate_pool_size, num_samples),
        random_state=random_state,
        replace=True,
    )
    iv_names = list(ordered_variable_keys(state.task))
    rows = []
    for row in pool.to_dict(orient="records"):
        signature = _candidate_signature(state.task, row)
        if signature in seen:
            continue
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=iv_names)

    frame = pd.DataFrame(rows)
    if state.model is None or state.experiment_data is None or len(state.experiment_data) < 6:
        return frame.head(num_samples).reset_index(drop=True)

    predictions = state.model.predict(frame[iv_names])
    if np.ndim(predictions) > 1:
        predictions = np.asarray(predictions)[:, 0]
    frame = frame.assign(predicted_score=np.asarray(predictions, dtype=float))
    frame = frame.sort_values("predicted_score", ascending=False).head(num_samples)
    return frame[iv_names].reset_index(drop=True)


def summarize_state(state: VehBenchState) -> dict:
    if state.experiment_data is None or state.experiment_data.empty:
        return {
            "task_id": state.task["task_id"],
            "queries": 0,
            "cycles": len(state.cycle_summaries),
            "feasible_found": False,
            "best_score": None,
            "best_frequency_error_pct": None,
            "best_candidate": None,
        }

    best_idx = state.experiment_data["score"].astype(float).idxmax()
    best_row = state.experiment_data.loc[best_idx]
    best_candidate = {
        key: float(best_row[key])
        for key in ordered_variable_keys(state.task)
    }
    return {
        "task_id": state.task["task_id"],
        "queries": int(len(state.experiment_data)),
        "cycles": int(len(state.cycle_summaries)),
        "feasible_found": bool(state.experiment_data["is_feasible"].any()),
        "best_score": round(float(best_row["score"]), 6),
        "best_frequency_error_pct": None
        if pd.isna(best_row["frequency_error_pct"])
        else round(float(best_row["frequency_error_pct"]), 6),
        "best_candidate": best_candidate,
        "best_cycle": str(best_row["cycle_label"]),
    }


def run_closed_loop_frequency_task(
    task: dict,
    initial_samples: int = 6,
    guided_rounds: int = 3,
    proposal_batch: int = 3,
    candidate_pool_size: int = 128,
    random_state: int = 0,
) -> tuple[VehBenchState, dict]:
    state = initialize_state(task)
    state = random_experimentalist(
        state,
        num_samples=initial_samples,
        random_state=random_state,
    )
    state = verifier_experiment_runner(state, cycle_label="bootstrap")
    theorist = make_score_theorist(random_state=random_state)

    for cycle_idx in range(guided_rounds):
        state = theorist(state)
        state = surrogate_guided_experimentalist(
            state,
            num_samples=proposal_batch,
            candidate_pool_size=candidate_pool_size,
            random_state=random_state + cycle_idx + 1,
        )
        state = verifier_experiment_runner(state, cycle_label=f"guided_{cycle_idx + 1}")
        if state.experiment_data is not None and not state.experiment_data.empty and bool(state.experiment_data["is_feasible"].any()):
            break

    return state, summarize_state(state)


def write_poc_outputs(
    state: VehBenchState,
    summary: dict,
    output_dir: str | Path,
) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary_path = output_path / "autora_poc_frequency_summary.json"
    traces_path = output_path / "autora_poc_frequency_traces.jsonl"
    report_path = output_path / "autora_poc_frequency_report.md"

    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    with traces_path.open("w") as handle:
        for trace in state.traces:
            handle.write(json.dumps(trace, ensure_ascii=False) + "\n")

    cycle_lines = []
    for item in state.cycle_summaries:
        cycle_lines.append(
            f"- `{item['cycle_label']}`: queries={item['query_count']}, "
            f"feasible={item['feasible_found']}, "
            f"best_score={item['best_score']}, "
            f"best_frequency_error_pct={item['best_frequency_error_pct']}"
        )
    worth_it = bool(summary["feasible_found"]) or (
        summary["best_frequency_error_pct"] is not None and summary["best_frequency_error_pct"] <= 5.0
    )
    report = "\n".join(
        [
            "# AutoRA POC Frequency Smoke",
            "",
            f"- task_id: `{summary['task_id']}`",
            f"- queries: `{summary['queries']}`",
            f"- cycles: `{summary['cycles']}`",
            f"- feasible_found: `{summary['feasible_found']}`",
            f"- best_score: `{summary['best_score']}`",
            f"- best_frequency_error_pct: `{summary['best_frequency_error_pct']}`",
            f"- best_cycle: `{summary['best_cycle']}`",
            f"- best_candidate: `{json.dumps(summary['best_candidate'], ensure_ascii=False)}`",
            f"- continuation_signal: `{'worth_continuing' if worth_it else 'not_yet_worth_continuing'}`",
            "",
            "## Cycle Summary",
            *cycle_lines,
        ]
    )
    report_path.write_text(report + "\n")
    return {
        "summary": summary_path,
        "traces": traces_path,
        "report": report_path,
    }
