# EH-LLM (EH-GPT)

## 中文简版目录

### 先看这几个文件

- [docs/PROJECT_HANDOFF.md](docs/PROJECT_HANDOFF.md)
  当前最重要的交接文档，包含真实用途、当前状态、已完成修复、远程环境、接手步骤。
- [docs/VEHBENCH_MASTER_EXECUTION_PLAN.md](docs/VEHBENCH_MASTER_EXECUTION_PLAN.md)
  `VEHBench` benchmark 论文与工程主线的执行总纲；包含目标范围、阶段拆解、当前状态、验收标准、实验矩阵和下一步顺序。
- [docs/vehbench_normalization_rules.md](docs/vehbench_normalization_rules.md)
  `VEHBench` 单位归一化和字段落库规则；后面做 extraction、candidate/silver/gold、verifier 回代时都以这份为准。
- [TASK_ROADMAP.md](TASK_ROADMAP.md)
  旧版通用路线图，保留作背景参考。
- [VEHBENCH_NEURIPS_DB_EXECUTION_BLUEPRINT.md](VEHBENCH_NEURIPS_DB_EXECUTION_BLUEPRINT.md)
  较早期的蓝图和实验背景，保留作补充参考。

### 这个项目现在实际在做什么

- 主题：振动能量采集（VEH）论文搜索、筛选、PDF 解析、结构化抽取。
- 实际主链路：
  `search_papers.py -> backfill_abstracts.py -> filter_01~04 -> cleanup_pdfs.py -> mineru_runner.py -> extract_schema.py`

### 当前真实状态

- 代码侧关键修复已完成：
  检索去重、stage4 写出逻辑、PDF cleanup、MinerU 状态机、远程部署脚本、extract/mineru 依赖声明。
- 数据侧尚未完全重建：
  当前仓库里的 stage4 / parsed / normalized / extracted 仍带有历史产物，和最新代码不完全一致。
- 远程环境已验证可用：
  远程 `openai` 与 `mineru` 已可导入，远程 venv 当前使用 `/root/ehllm-venv`。

### 接手时优先看的入口

- `pipelines/download/search_papers.py`
- `pipelines/download/filtering/filter_04_llm_score.py`
- `pipelines/download/cleanup_pdfs.py`
- `ingestion/mineru_runner.py`
- `pipelines/extract/extract_schema.py`
- `scripts/deploy_remote.sh`
- `scripts/run_remote.sh`
- `scripts/fetch_remote.sh`

### 推荐继续顺序

1. 先读 `docs/PROJECT_HANDOFF.md`
2. 再重建 `papers.jsonl -> stage04`
3. 然后修正/确认 `pdf_path`
4. 再跑 `mineru_runner.py`
5. 最后跑 `extract_schema.py`

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
