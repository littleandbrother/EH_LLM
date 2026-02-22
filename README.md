# EH-LLM (EH-GPT)

> **Physical-AI System Builder** — Energy Harvesting + TinyML + LLM + System Automation

A domain-specific LLM system for **vibration energy harvester** design assistance.
EH-GPT extracts structured knowledge from literature, normalizes heterogeneous data,
and provides evidence-based design recommendations with full citation tracing.

---

## 🎯 Project Goals

| # | Goal | Metric |
|---|------|--------|
| 1 | **论文可发表** | Nature 子刊级 |
| 2 | **系统可复现** | 工程可信，端到端 Pipeline |
| 3 | **能力可迁移** | LLM / Physical-AI 岗位认可 |

---

## 📂 Directory Structure

```
eh-llm/
├── schemas/           # EH 领域 Schema 定义 (eh_schema_v1.yaml)
├── pipelines/         # 数据处理 Pipeline
│   ├── download/      # Semantic Scholar 自动下载
│   ├── parse/         # PDF → Structured Text (GROBID)
│   ├── extract/       # LLM 字段抽取
│   └── normalize/     # 单位归一化 Engine
├── experiments/       # 实验定义 YAML
├── runs/              # 实验运行记录 (自动生成)
├── data_registry/     # 统一数据注册中心
│   ├── raw/           # 原始 PDF
│   ├── parsed/        # 解析后 TEI/JSON
│   ├── extracted/     # 抽取后结构数据
│   ├── gold/          # Gold 标注数据
│   └── sft/           # SFT 训练数据
├── artifacts/         # 模型权重 & 评测报告
│   ├── checkpoints/
│   └── reports/
├── tools/             # CLI: ehllm plan | run | report | publish
├── docs/              # 文档 (normalization_rules.md 等)
└── paper/             # 论文写作 & Figures
```

---

## ⚙️ Core Principles

1. **不允许直接实验** — 一切通过 `experiment.yaml`
2. **一切生成 `run_id`** — 完全可追溯
3. **先建系统，再做模型** — Experiment OS first

---

## 🚀 Quick Start

```bash
# 计划实验
ehllm plan --config experiments/my_experiment.yaml

# 运行实验
ehllm run --config experiments/my_experiment.yaml

# 生成报告
ehllm report --run-id <RUN_ID>

# 发布结果
ehllm publish --run-id <RUN_ID>
```

---

## 📅 Timeline

| Phase | Description | Duration |
|-------|-------------|----------|
| 0 | 项目初始化 | 1 周 |
| 1 | EH 领域知识标准化 | 2–3 周 |
| 2 | 文献解析与知识抽取 | 3–4 周 |
| 3 | Gold 数据构建 | 3 周 |
| 4 | SFT 训练 (EH-GPT) | 2–3 周 |
| 5 | 推理系统 | 2 周 |
| 6 | Evaluation & Failure Analysis | 3 周 |
| 7 | Demo Case | 2 周 |

See [TASK_ROADMAP.md](TASK_ROADMAP.md) for the full task checklist.
