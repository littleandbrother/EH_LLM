# 📋 EH-LLM (EH-GPT) 完整任务路线图

> **目标**: ✅ 论文可发表（子刊级） · ✅ 系统可复现 · ✅ 能力可迁移  
> **预计总时长**: 6–7 个月  
> **最后更新**: 2026-02-22

---

## 状态说明

| 标记 | 含义 |
|------|------|
| ⬜ | 未开始 |
| 🔵 | 进行中 |
| ✅ | 已完成 |
| ⏸️ | 暂停 |
| ❌ | 取消/废弃 |

---

## PHASE 0 — 项目初始化（1 周）

> 🎯 建立 Experiment OS（实验操作系统）

| Task | 描述 | 交付物 | 状态 | 备注 |
|------|------|--------|------|------|
| 0.1 | 建立主仓库（唯一事实源） | `eh-llm/` 完整目录结构 | 🔵 | 当前任务 |
| 0.2 | Git 规则制定 | `.gitignore`, branch strategy (`main`/`dev`/`exp/*`) | ⬜ | 铁律：不允许直接实验 |
| 0.3 | 实验 CLI（第一优先） | `tools/` — `ehllm plan/run/report/publish` | ⬜ | 未来所有工作的入口 |

---

## PHASE 1 — EH 领域知识标准化（2–3 周）⭐论文核心

> 🎯 建立 Energy Harvester 统一描述体系

| Task | 描述 | 交付物 | 状态 | 备注 |
|------|------|--------|------|------|
| 1.1 | **定义 Energy Harvester Schema**（最重要） | `schemas/eh_schema_v1.yaml` | ✅ | 7-level physics-aware schema, 54+ fields, phased priorities |
| 1.2 | 指标口径统一规则 | `docs/normalization_rules.md` | ⬜ | Vrms, P_norm 等 — 论文 novelty 之一 |
| 1.3 | Semantic Scholar 自动下载 Pipeline | `pipelines/download/`, `data_registry/papers.jsonl` | ⬜ | 目标 300–500 篇 vibration EH |

---

## PHASE 2 — 文献解析与知识抽取（3–4 周）

> 🎯 从 PDF 到结构化知识

| Task | 描述 | 交付物 | 状态 | 备注 |
|------|------|--------|------|------|
| 2.1 | PDF → Structured Text | `tei.xml`, `sections.json` | ⬜ | 部署 GROBID |
| 2.2 | Chunk + Evidence Pointer | chunk_id / text / page / figure_id / table_id / paper_id | ⬜ | |
| 2.3 | 自动字段抽取（Baseline） | LLM + prompt extraction → frequency, power, volume 等 | ⬜ | 先不训练，Baseline only |
| 2.4 | 单位归一化 Engine | `pipelines/normalize/` | ⬜ | mW→W, mm³→cm³, peak→rms |

---

## PHASE 3 — Gold 数据构建（3 周）⭐决定论文高度

> 🎯 构建高质量标注数据集

| Task | 描述 | 交付物 | 状态 | 备注 |
|------|------|--------|------|------|
| 3.1 | Gold 标注任务生成 | `gold_tasks.json` (evidence + question + expected_schema) | ⬜ | 自动生成 |
| 3.2 | 专家标注 | ≥500–1000 gold samples | ⬜ | 你 + EH collaborator |
| 3.3 | Inter-Annotator Agreement | IAA, Cohen κ, numeric deviation | ⬜ | |
| 3.4 | Gold → SFT Dataset | `eh_sft_dataset_v1` (instruction/input/output/evidence) | ⬜ | |

---

## PHASE 4 — SFT 训练 · EH-GPT 诞生（2–3 周）

> 🎯 微调出 EH 领域专用模型

| Task | 描述 | 交付物 | 状态 | 备注 |
|------|------|--------|------|------|
| 4.1 | 选择基座模型 | 3B first → 7B later | ⬜ | |
| 4.2a | **SFT-E（Extraction）** | paper → structured EH data | ⬜ | 必须与 SFT-R 分开 |
| 4.2b | **SFT-R（Reasoning）** | design query → cited recommendation | ⬜ | 必须与 SFT-E 分开 |
| 4.3 | 远端 GPU 训练 | checkpoints, train logs | ⬜ | train + save + upload |

---

## PHASE 5 — EH-GPT 推理系统（2 周）

> 🎯 构建端到端推理 Pipeline

| Task | 描述 | 交付物 | 状态 | 备注 |
|------|------|--------|------|------|
| 5.1 | RAG System | query → retrieve → context → EH-GPT → cited answer | ⬜ | |
| 5.2 | Constraint Checker | physics consistency / frequency feasibility / power scaling | ⬜ | |
| 5.3 | **Evidence Tracing**（必须） | claim → citation → page | ⬜ | |

---

## PHASE 6 — Evaluation & Failure Analysis（3 周）⭐子刊关键

> 🎯 系统性评测 + 失败分析 = 可信度

| Task | 描述 | 交付物 | 状态 | 备注 |
|------|------|--------|------|------|
| 6.1 | Extraction Benchmark | GPT-4 vs RAG vs EH-GPT (F1) | ⬜ | |
| 6.2 | Design Reasoning Benchmark | constraint satisfaction / citation precision / hallucination rate | ⬜ | |
| 6.3 | **Ablation**（必须） | 去掉 SFT / normalization / evidence → 观察下降 | ⬜ | |
| 6.4 | Failure Taxonomy | wrong unit / missing condition / unsupported claim / over extrapolation | ⬜ | |

---

## PHASE 7 — Demo Case · 论文最后一图（2 周）

> 🎯 真实设计案例展示

| Task | 描述 | 交付物 | 状态 | 备注 |
|------|------|--------|------|------|
| 7.1 | 端到端 Design Demo | 输入 "design walking energy harvester" → candidates + range + citations | ⬜ | |
| 7.2 | 专家评审 | feasible ✅ · reasonable ✅ | ⬜ | |

---

## 📊 论文结构映射

| Figure | 内容 | 对应 Phase |
|--------|------|-----------|
| Fig 1 | Overall EH-GPT Architecture | 0, 5 |
| Fig 2 | Dataset + Schema | 1, 3 |
| Fig 3 | Extraction + SFT-E | 2, 4 |
| Fig 4 | Reasoning + SFT-R | 4, 5 |
| Fig 5 | Reliability & Failure Analysis | 6 |
| Fig 6 | Real Design Demo | 7 |

---

## ⏱️ 时间总览

| 阶段 | 内容 | 预计时间 |
|------|------|---------|
| 基础系统 | Phase 0–1 | 1 个月 |
| 数据 + Gold | Phase 2–3 | 2 个月 |
| 训练 | Phase 4 | 1 个月 |
| 评测 | Phase 5–6 | 1 个月 |
| 写作 | Phase 7 + Paper | 1 个月 |
| **总计** | | **≈ 6–7 个月** |
