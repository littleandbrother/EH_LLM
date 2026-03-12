#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


REPO_ROOT = Path(__file__).resolve().parents[1]
EXP_ROOT = REPO_ROOT.parent / "EH-LLM-vehbench-exp"
OUT_DIR = REPO_ROOT / "artifacts/paper_submission"
FIG_DIR = OUT_DIR / "figures"


def ensure_dirs() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict]:
    with path.open() as handle:
        return [json.loads(line) for line in handle]


def plot_funnel() -> dict:
    cleaned_rows = read_jsonl(EXP_ROOT / "data_registry/papers_stage04_core_corpus_paper_pdf_cleaned.jsonl")
    normalized = {p.stem for p in (EXP_ROOT / "normalized_docs").glob("*.json")}
    parsed_success = sum(1 for row in cleaned_rows if row.get("pdf_path") and Path(row["pdf_path"]).stem in normalized)
    counts = [
        ("Metadata", 1908),
        ("Stage 1", 1104),
        ("Stage 2", 820),
        ("Stage 3", 301),
        ("Stage 4", 236),
        ("PDF aligned", 199),
        ("Parsed", parsed_success),
        ("Valid extract", 186),
        ("Curated gold", 55),
        ("Tasks", 162),
    ]
    df = pd.DataFrame(counts, columns=["stage", "count"])
    plt.figure(figsize=(10, 5.5))
    ax = sns.barplot(data=df, x="count", y="stage", palette="crest")
    ax.set_title("VEHBench Source-to-Task Funnel")
    ax.set_xlabel("Count")
    ax.set_ylabel("")
    for idx, value in enumerate(df["count"]):
        ax.text(value + max(df["count"]) * 0.01, idx, f"{value}", va="center", fontsize=9)
    plt.tight_layout()
    path = FIG_DIR / "funnel_overview.png"
    plt.savefig(path, dpi=220)
    plt.close()
    return {"path": path, "counts": counts}


def plot_task_inventory() -> dict:
    tasks = read_jsonl(REPO_ROOT / "data_registry/benchmark/tasks_paper_grounded.jsonl")
    counter = Counter((task["task_type"], (task.get("split") or {}).get("name")) for task in tasks)
    rows = []
    for (task_type, split), count in sorted(counter.items()):
        rows.append({"task_type": task_type, "split": split, "count": count})
    df = pd.DataFrame(rows)
    pivot = df.pivot(index="split", columns="task_type", values="count").fillna(0).reindex(
        ["train", "val", "test-id", "test-ood"]
    )
    pivot = pivot[["frequency_matching", "constrained_power_maximization", "feasibility_repair"]]
    ax = pivot.plot(kind="bar", stacked=True, figsize=(9, 5), color=["#2B8CBE", "#F4A259", "#6A994E"])
    ax.set_title("Task Inventory by Split and Task Type")
    ax.set_xlabel("")
    ax.set_ylabel("Task Count")
    ax.legend(title="", labels=["Frequency", "Power", "Repair"], frameon=False)
    for container in ax.containers:
        ax.bar_label(container, label_type="center", color="white", fontsize=8)
    plt.tight_layout()
    path = FIG_DIR / "task_inventory.png"
    plt.savefig(path, dpi=220)
    plt.close()
    return {"path": path, "counts": rows}


def plot_verifier_summary() -> dict:
    backsub = read_json(EXP_ROOT / "data_registry/benchmark/verifier_v1_backsub_summary.json")
    audit_rows = read_jsonl(EXP_ROOT / "data_registry/benchmark/power_condition_audit.jsonl")
    kept = sum(1 for row in audit_rows if row.get("decision") == "keep")
    total = len(audit_rows)

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8))

    freq_df = pd.DataFrame(
        [
            {"setting": "Raw", "mape_pct": backsub["literature_backsub_raw"]["frequency_mape_pct"]},
            {
                "setting": "Calibrated",
                "mape_pct": backsub["literature_backsub_calibrated_frequency"]["frequency_mape_pct"],
            },
        ]
    )
    sns.barplot(data=freq_df, x="setting", y="mape_pct", palette=["#B23A48", "#2A9D8F"], ax=axes[0])
    axes[0].set_yscale("log")
    axes[0].set_title("Frequency Back-Substitution Error")
    axes[0].set_ylabel("MAPE (%) [log scale]")
    axes[0].set_xlabel("")
    for idx, value in enumerate(freq_df["mape_pct"]):
        axes[0].text(idx, value * 1.05, f"{value:.1f}%", ha="center", va="bottom", fontsize=9)

    audit_df = pd.DataFrame(
        [
            {"bucket": "Ready mappings", "count": 52},
            {"bucket": "Power-gold subset", "count": kept},
        ]
    )
    sns.barplot(data=audit_df, x="bucket", y="count", palette=["#577590", "#43AA8B"], ax=axes[1])
    axes[1].set_title("Power Audit Coverage")
    axes[1].set_ylabel("Paper Count")
    axes[1].set_xlabel("")
    for idx, value in enumerate(audit_df["count"]):
        axes[1].text(idx, value + 0.5, f"{value}", ha="center", va="bottom", fontsize=9)
    axes[1].text(
        0.5,
        max(audit_df["count"]) * 0.55,
        f"{kept}/{total} kept\nfor audited power subset",
        ha="center",
        va="center",
        fontsize=10,
        color="#1D3557",
    )

    fig.suptitle("Verifier v1 Calibration Summary", y=1.02)
    plt.tight_layout()
    path = FIG_DIR / "verifier_calibration_summary.png"
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()
    return {"path": path}


def plot_main_success_heatmap() -> dict:
    data = read_json(REPO_ROOT / "artifacts/reports/main_benchmark_comparison_v1.json")
    cols = [
        ("frequency_matching::test-id", "Freq-ID"),
        ("frequency_matching::test-ood", "Freq-OOD"),
        ("feasibility_repair::test-id", "Repair-ID"),
        ("feasibility_repair::test-ood", "Repair-OOD"),
    ]
    solver_order = [
        ("random_search", "Random"),
        ("genetic_algorithm", "GA"),
        ("cma_es", "CMA-ES"),
        ("bayesian_optimization", "BO"),
        ("zero_shot_llm", "Kimi Zero-Shot"),
        ("verifier_guided_llm", "Kimi Verifier-Guided"),
    ]
    matrix = []
    idx_labels = []
    for solver_key, label in solver_order:
        row = []
        for block_key, _ in cols:
            row.append(data[block_key]["rows"][solver_key]["success_rate"])
        matrix.append(row)
        idx_labels.append(label)
    df = pd.DataFrame(matrix, index=idx_labels, columns=[label for _, label in cols])
    plt.figure(figsize=(8.5, 4.8))
    ax = sns.heatmap(df, annot=True, fmt=".3f", cmap="YlGnBu", vmin=0.0, vmax=1.0, cbar_kws={"label": "Success Rate"})
    ax.set_title("Main Benchmark Success Rates")
    ax.set_xlabel("")
    ax.set_ylabel("")
    plt.tight_layout()
    path = FIG_DIR / "main_success_heatmap.png"
    plt.savefig(path, dpi=220)
    plt.close()
    return {"path": path}


def plot_ood_pareto() -> dict:
    data = read_json(REPO_ROOT / "artifacts/reports/main_benchmark_comparison_v1.json")
    blocks = [
        ("frequency_matching::test-ood", "Frequency OOD"),
        ("feasibility_repair::test-ood", "Repair OOD"),
    ]
    solver_order = [
        ("random_search", "Random", "#457B9D"),
        ("genetic_algorithm", "GA", "#E76F51"),
        ("cma_es", "CMA-ES", "#6D597A"),
        ("bayesian_optimization", "BO", "#2A9D8F"),
        ("zero_shot_llm", "Kimi Zero-Shot", "#F4A261"),
        ("verifier_guided_llm", "Kimi Verifier-Guided", "#1D3557"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    for ax, (block_key, title) in zip(axes, blocks):
        rows = data[block_key]["rows"]
        for solver_key, label, color in solver_order:
            row = rows[solver_key]
            q = row["avg_queries_to_success"]
            if q is None:
                q = row["task_count"]
            ax.scatter(q, row["success_rate"], s=90, color=color, label=label)
            ax.text(q + 0.08, row["success_rate"] + 0.01, label, fontsize=8)
        ax.set_title(title)
        ax.set_xlabel("Avg Queries To Success")
        ax.grid(alpha=0.25)
    axes[0].set_ylabel("Success Rate")
    fig.suptitle("OOD Pareto View: Success vs Query Cost", y=1.02)
    plt.tight_layout()
    path = FIG_DIR / "ood_pareto.png"
    plt.savefig(path, dpi=220, bbox_inches="tight")
    plt.close()
    return {"path": path}


def main() -> None:
    ensure_dirs()
    outputs = {
        "funnel": plot_funnel(),
        "task_inventory": plot_task_inventory(),
        "verifier_calibration": plot_verifier_summary(),
        "main_success_heatmap": plot_main_success_heatmap(),
        "ood_pareto": plot_ood_pareto(),
    }
    summary_path = OUT_DIR / "figure_manifest.json"
    summary_path.write_text(json.dumps(outputs, indent=2, default=str))
    print(json.dumps({"figure_dir": str(FIG_DIR), "manifest": str(summary_path)}, indent=2))


if __name__ == "__main__":
    sns.set_theme(style="whitegrid", context="talk")
    main()
