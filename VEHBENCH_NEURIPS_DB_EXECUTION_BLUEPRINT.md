# VEHBench NeurIPS D&B 执行蓝图

## 0. 文档目的

这份文档不是“投稿灵感”，而是一份可执行的硬门槛蓝图。目标不是口头上把成功率说成 80%，而是把项目做到“只有在满足一组极严苛的内部验收条件时才投稿”。这里的“80%风格”指：

- 只在通过全部内部硬门槛后才投 `NeurIPS Datasets and Benchmarks`
- 论文主轴严格收敛到 `physics-grounded benchmark + verifier-guided agent`
- 不把 `接口电路自动设计`、`固件代码生成`、`CAD 自动脚本生成` 塞进同一篇主线

## 1. 论文定位

### 1.1 推荐题目

`VEHBench: A Physics-Grounded Benchmark and Verifier-Guided Language Agent for Vibration Energy Harvester Inverse Design`

### 1.2 推荐轨道

优先投 `NeurIPS Datasets and Benchmarks Track`，不是 Main。

原因：

- 你的 strongest contribution 应该是 `benchmark + environment + protocol + strong baselines`
- D&B 明确接受数据集、benchmark、environment、benchmarking methodology、工具链
- D&B 现在要求投稿时就提供数据和代码访问入口，正好逼你把 artifact 做扎实

### 1.3 论文要解决的唯一核心问题

给定：

- 激励条件，如频率范围、加速度、频谱类型
- 结构约束，如长度、宽度、厚度、体积、应力上限
- 材料与制造约束
- 负载或标准化接口假设
- 查询预算

现有 LLM、黑盒优化器和零散工程经验缺少一个：

- 足够快
- 足够可信
- 可复现
- 可大规模公平比较

的 `VEH inverse design` 评测环境。

## 2. 论文范围收缩

### 2.1 v1 必须只做的范围

只收敛到这类设备：

- `piezoelectric cantilever` 为主
- 线性小振幅模型
- 可选 `tip mass`
- `unimorph` 或 `bimorph`
- 激励以 `sinusoidal` 和 `narrow-band measured trace` 为主
- 负载先统一到 `resistive load` 或一个标准整流接口假设

### 2.2 v1 明确不做

- 非线性双稳态
- 磁耦合强非线性
- 超材料、阵列、柔性纺织、复杂多自由度结构
- 开放式 CAD 生成
- 电路自动综合
- 固件自动生成

理由：这些方向不是没价值，而是会稀释 NeurIPS D&B 的主线。

## 3. 投稿前必须通过的硬门槛

只有全部满足，才提交。

### 3.1 数据与任务规模门槛

| 项目 | 最低门槛 | 理想门槛 |
|---|---:|---:|
| OpenAlex + Semantic Scholar 初始候选论文 | 8,000 | 15,000+ |
| 去重后候选论文 | 4,000 | 7,000 |
| 可合法获取 PDF 的论文 | 1,500 | 2,500 |
| 成功结构化解析全文 | 800 | 1,500 |
| 可提取完整关键参数的候选论文 | 450 | 800 |
| 通过物理一致性校验的黄金论文 | 250 | 500 |
| 文献驱动真实任务 | 800 | 1,500 |
| 合成任务 | 6,000 | 15,000 |
| 最终公开评测集 | 5,000 | 8,000 |
| OOD 任务比例 | 20% | 30% |
| FEM transfer case | 50 | 100 |
| 真实样机验证 case | 10 | 20-40 |
| Agent 轨迹总数 | 20,000 | 50,000+ |
| 成功 SFT 样本 | 8,000 | 20,000+ |

### 3.2 verifier 可信度门槛

对黄金论文和外部校准集：

- 固有频率误差中位数 `< 5%`
- 固有频率 90 分位误差 `< 10%`
- 功率误差中位数 `< 10%`
- 功率 90 分位误差 `< 20%`
- 应力或位移约束方向性判断准确率 `> 90%`
- 对 FEM transfer 的排名相关性 `Spearman > 0.85`

### 3.3 benchmark 可信度门槛

- 所有任务都有明确输入、约束、预算、评价指标
- train/val/test/OOD split 固定且公开
- baseline 统一查询预算
- 不允许私有提示词优势污染结果
- 任务分布可视化完整
- 至少 3 个外部研究者可独立跑通主结果

### 3.4 论文结果门槛

至少满足以下 4 条中的 3 条：

- verifier-guided LLM 相比 zero-shot LLM，`CSR` 提升 `>= 15` 个百分点
- verifier-guided LLM 相比 scalar-reward 版本，平均迭代数下降 `>= 30%`
- distilled 8B 相比 teacher，在 `>= 80%` 性能下，推理成本下降 `>= 5x`
- 传统优化器在 OOD 任务上系统性退化，而 verifier-guided LLM 保持更高鲁棒性

### 3.5 artifact 门槛

- 投稿时公开 `code + data + eval scripts + model card + dataset card`
- 数据托管到 `Hugging Face`、`Kaggle`、`Dataverse` 或 `OpenML`
- 附带 `Croissant metadata`
- 开源许可、数据许可、来源许可写清楚
- 所有外部 API 使用和再分发边界写清楚

## 4. 推荐数据底座规模

### 4.1 文献层

建议把数据分成 4 层：

1. `raw_metadata`
   - 只含 OpenAlex 和 Semantic Scholar 拉下来的元数据
2. `raw_pdf_registry`
   - 记录每篇文章的 PDF 来源、许可、抓取状态
3. `parsed_papers`
   - 结构化段落、表格、图注、候选参数
4. `gold_papers`
   - 通过物理交叉验证的最终样本

### 4.2 benchmark 层

建议公开：

- `VEH-Eval-ID-3000`
- `VEH-Eval-OOD-1000`
- `VEH-Eval-Trace-1000`

其中：

- `ID` 用于标准评测
- `OOD` 测试分布外泛化
- `Trace` 保留多轮反馈过程，用于 agent 分析

### 4.3 训练层

训练集建议分三类：

- `paper-grounded tasks`
- `physics-synthetic tasks`
- `teacher-generated repair traces`

比例建议：

- 文献任务 20%
- 合成任务 50%
- 轨迹蒸馏样本 30%

## 5. 论文实验表格设计

### Table 1. Benchmark Summary

展示内容：

- 任务数量
- 任务类型
- 参数维度
- 约束种类
- 数据来源比例
- ID/OOD 划分

### Table 2. Verifier Validation Against Literature, FEM, and Hardware

列：

- dataset split
- number of cases
- frequency MAPE
- power MAPE
- stress decision accuracy
- rank correlation

行：

- gold papers
- FEM transfer
- hardware transfer

### Table 3. Main Benchmark Results

方法：

- Random Search
- GA
- CMA-ES
- Bayesian Optimization
- Zero-shot LLM
- RAG LLM
- Verifier-guided LLM
- Distilled 8B

指标：

- CSR
- best normalized objective
- avg queries to success
- wall-clock
- dollar cost or token cost

### Table 4. OOD Generalization

OOD 维度：

- unseen excitation range
- unseen geometry regime
- unseen material combination
- unseen load setting

### Table 5. Ablation Study

变量：

- no retrieval
- no verifier
- scalar reward only
- structured feedback
- no trajectory distillation
- literature-only training
- synthetic-only training

### Table 6. Reproducibility and Artifact Readiness

列：

- artifact item
- released at submission
- deterministic script available
- estimated rerun time

## 6. 论文图设计

### Figure 1. Problem and System Overview

必须画成一张总图：

- 输入任务规范
- agent 提议参数
- physics verifier 返回结构化反馈
- 迭代优化
- top candidate 进入 FEM 和硬件验证
- 轨迹被蒸馏进小模型

这张图是整篇论文的锚点。

### Figure 2. Data Funnel

展示：

- 元数据候选数
- 可获取 PDF 数
- 可解析全文数
- 参数完整数
- 物理自洽数
- 最终 benchmark 任务数

### Figure 3. Verifier Formulation

画一个从参数到输出的图：

- beam geometry
- equivalent mass
- stiffness
- electromechanical coupling
- outputs: frequency, displacement, stress, power

### Figure 4. Benchmark Distribution

至少 4 个子图：

- resonance frequency distribution
- acceleration distribution
- geometry distribution
- material/load distribution

### Figure 5. Main Results Frontier

建议画 Pareto 图：

- x 轴为 avg queries
- y 轴为 CSR
- 点大小为 wall-clock 或 token cost

### Figure 6. Verifier to FEM/Hardware Transfer

两个散点图：

- verifier vs FEM
- verifier vs hardware

分别针对：

- frequency
- power

### Figure 7. Qualitative Repair Trajectory

展示一条典型失败到成功轨迹：

- 初始参数不满足频率约束
- verifier 给出结构化原因
- 第二步修正长度或质量
- 第三步满足频率但应力超限
- 第四步成功

注意：这里展示的是 `error attribution -> action revision`，不是大段思维链。

## 7. 9 页正文分配

按 NeurIPS 风格，正文极度紧凑，建议这样切：

### Page 1

- 标题
- 摘要
- 引言前半
- Figure 1

### Page 2

- 引言后半
- 贡献点
- 问题定义

### Page 3

- benchmark task definition
- 数据来源与数据漏斗
- Figure 2

### Page 4

- verifier 建模与假设
- Figure 3

### Page 5

- agent loop
- retrieval
- trajectory distillation

### Page 6

- 实验设置
- baseline 公平性说明
- Table 1
- Table 2

### Page 7

- 主结果
- Table 3
- Figure 5

### Page 8

- OOD 和消融
- Table 4
- Table 5

### Page 9

- FEM/hardware transfer
- Figure 6
- Figure 7
- 局限性和 broader impact 的简短收尾

附录放：

- 推导细节
- 额外图表
- 任务模板
- 提示词
- 超参数
- 许可说明

## 8. 从论文获取到 SFT 的完整数据管线

## 8.1 总体原则

不要直接从互联网胡乱抓 PDF。必须把合法性、可重现性、可追溯性写进流水线。

优先级：

1. OpenAlex 用于 `发现 + OA PDF 定位 + 许可字段`
2. Semantic Scholar 用于 `补充元数据 + 引文扩展 + paper search`
3. 仅下载明确可访问且许可边界清楚的 PDF
4. 非 OA 论文只保留元数据和手工摘要，不私自镜像全文

## 8.2 推荐目录结构

```text
vehbench/
  data/
    raw/
      openalex/
      semantic_scholar/
      pdf_registry/
      pdfs/
    interim/
      deduped_metadata/
      parsed_json/
      tables/
      figures/
      extraction_runs/
    processed/
      gold_papers/
      task_specs/
      benchmark_splits/
      rag_corpus/
      teacher_traces/
      sft_data/
  configs/
    queries/
    schemas/
    prompts/
  scripts/
    collect/
    parse/
    validate/
    generate/
    train/
```

## 8.3 文献检索阶段

### Step 1. 定义种子查询

先用 20 到 30 个高精度查询，不追求第一轮全召回。

建议种子关键词：

- `"piezoelectric energy harvester" cantilever tip mass`
- `"vibration energy harvester" cantilever`
- `"piezoelectric cantilever harvester" proof mass`
- `"unimorph" piezoelectric harvester`
- `"bimorph" piezoelectric harvester`
- `"base excitation" piezoelectric harvester`
- `"resistive load" "piezoelectric energy harvester"`

排除词在清洗阶段做，不要在第一步搜索写得过于激进。

### Step 2. OpenAlex 发现候选

优先使用：

- `/works` 的 `title_and_abstract.search`
- `publication_year`
- `has_oa_accepted_or_published_version`
- `best_oa_location.license`
- `locations.source.type`

实践建议：

- `per-page=200`
- 用 `select=` 只拿必要字段
- 记录 `doi`、`openalex id`、`best_oa_location.pdf_url`、`license`
- 所有请求都带 API key
- 做全局重试与速率控制

### Step 3. Semantic Scholar 补强与扩展

用法：

- `paper/search/bulk` 查同义表达
- 用 `fields=` 拿 `title,abstract,year,venue,citationCount,openAccessPdf,externalIds`
- 沿引用和被引扩展
- 把高影响力综述和标准实验论文拉进来做 query expansion

Semantic Scholar 更适合做：

- query expansion
- citation neighborhood
- metadata completion

### Step 4. 去重

按以下优先级建立 canonical paper record：

1. DOI 完全一致
2. arXiv/ACL/CorpusId/OpenAlex ID 映射
3. 规范化标题完全匹配
4. 标题 + 年份 + 第一作者模糊匹配

去重产物：

- `paper_uid`
- `source_ids`
- `preferred_metadata_source`

## 8.4 PDF 获取与合规

### Step 5. 只抓合法可访问 PDF

允许：

- OpenAlex `best_oa_location.pdf_url`
- OpenAlex content endpoint
- Semantic Scholar `openAccessPdf`
- 作者主页或官方仓库中明确开放的 PDF

不允许：

- 绕过出版社权限
- 批量镜像非开放论文全文

每个 PDF 必须记录：

- paper_uid
- download_url
- download_time
- license
- source
- sha256
- fetch_status

## 8.5 PDF 解析与结构化

### Step 6. 文档解析

推荐栈：

- `GROBID` 提取结构化全文与参考文献
- `PyMuPDF` 提取页面文本与版面位置
- `Camelot` 或 `tabula` 提取规则表格
- OCR 只对少数扫描件兜底

产物：

- section-level JSON
- table JSON
- figure caption JSON
- reference list

### Step 7. 第一阶段分类

先做一个 rule-based + 小模型分类器，标签如下：

- `include_linear_piezo_cantilever`
- `exclude_non_linear`
- `exclude_array_or_textile`
- `exclude_insufficient_geometry`
- `exclude_no_experimental_numbers`
- `manual_review`

这一阶段宁可高召回，不要过早扔掉边界样本。

### Step 8. 第二阶段字段提取

目标不是“摘要总结”，而是提成严格 JSON。

推荐字段：

```json
{
  "paper_uid": "",
  "device_type": "unimorph|bimorph",
  "transduction": "piezoelectric",
  "beam_length_mm": null,
  "beam_width_mm": null,
  "substrate_thickness_um": null,
  "piezo_thickness_um": null,
  "tip_mass_g": null,
  "proof_mass_dimensions_mm": null,
  "youngs_modulus_gpa": null,
  "density_kg_m3": null,
  "piezo_d31_pm_v": null,
  "load_resistance_ohm": null,
  "base_acceleration_ms2": null,
  "base_acceleration_g": null,
  "resonant_frequency_hz": null,
  "power_uw": null,
  "voltage_v": null,
  "stress_mpa": null,
  "excitation_type": "sinusoidal|swept|measured",
  "evidence_spans": []
}
```

要求：

- 所有字段必须带单位
- 单位统一归一化
- 记录原文证据 span
- 缺失字段不瞎补

### Step 9. 手工审核最小化策略

人工只审三类：

- 高频高价值综述/代表性论文
- 模型判定冲突样本
- 接近入库阈值的边界样本

目标是把人工成本集中在最影响黄金数据质量的地方。

## 8.6 物理一致性清洗

### Step 10. 先建立 v1 verifier

v1 输出：

- fundamental frequency
- tip displacement
- root stress
- load power
- 主要约束违规原因

### Step 11. 文献参数回代验证

将提取字段送入 verifier：

- 若固有频率误差过大，标记为 `geometry/material inconsistency`
- 若功率误差过大，标记为 `electrical/load inconsistency`
- 若字段缺失导致不确定性过高，标记为 `insufficient for gold`

黄金论文入库阈值建议：

- 关键几何字段完整
- 激励与负载信息完整
- 频率误差 `< 15%`
- 功率误差 `< 25%`

如果只满足频率但功率对不上，可作为 `silver`，不要进 `gold`。

## 8.7 benchmark 构建

### Step 12. 从黄金论文生成 paper-grounded tasks

每篇黄金论文可生成多类任务：

- 给定目标频率和尺寸约束，找满足约束的参数
- 给定激励和体积约束，最大化功率
- 给定功率目标，最小化体积或应力风险
- 给定固定材料，调整几何和负载

每个任务必须包括：

- problem statement
- search space bounds
- hard constraints
- objective
- verifier config
- query budget

### Step 13. 生成 synthetic tasks

在黄金论文支持的物理区间内做分层采样：

- `Latin Hypercube Sampling`
- log-scale 采样电阻和厚度
- 对材料组合做分层
- 保证每个桶的频率和尺寸都有覆盖

合成任务类型：

- `ID`: 在训练分布内采样
- `OOD-geometry`
- `OOD-excitation`
- `OOD-load`

### Step 14. 做数据切分

禁止泄漏：

- 同一篇论文衍生的任务不能跨 train/test
- 高相似参数簇不能同时出现在 train 和 OOD test
- teacher traces 不能从 test 任务生成

## 8.8 RAG 语料库

### Step 15. 构建 RAG 文档块

每篇论文切成：

- abstract
- method
- geometry paragraph
- experiment setup
- results paragraph
- extracted table rows

chunk metadata：

- paper_uid
- year
- venue
- transduction
- geometry class
- excitation class
- whether_gold

不要把整篇 PDF 直接塞进向量库。

## 8.9 teacher 轨迹生成

### Step 16. 设计交互协议

teacher 每一轮输入包括：

- task spec
- 当前候选参数
- 最近一次 verifier 输出
- 可选检索片段

teacher 每一轮输出限定为 JSON：

```json
{
  "analysis_summary": "简短原因归纳",
  "parameter_update": {
    "beam_length_mm": 32.0,
    "tip_mass_g": 0.45,
    "load_resistance_ohm": 68000
  },
  "expected_effect": "降低固有频率并提高匹配负载下功率"
}
```

重点：

- 训练的是 `error attribution + next action`
- 不是收集冗长自由思维链

### Step 17. 轨迹筛选

只保留：

- 最终成功的轨迹
- 3 到 8 步内收敛的高质量轨迹
- 每步修改幅度合理的轨迹

过滤掉：

- 乱跳参数
- 依赖 prompt hack
- 明显记忆化复述文献答案

## 8.10 SFT 数据集构造

### Step 18. SFT 样本格式

推荐两种任务格式：

1. `single-step repair`
   - 输入：任务 + 当前状态 + verifier feedback
   - 输出：下一步参数修正
2. `first-shot proposal`
   - 输入：任务 + 检索上下文
   - 输出：首个参数提案

推荐配比：

- 60% repair
- 25% first-shot proposal
- 15% failure explanation

### Step 19. 数据清洗

SFT 前做以下过滤：

- 去掉和 test 任务同源的样本
- 去掉输出非法 JSON 的样本
- 去掉 teacher 自相矛盾样本
- 对成功轨迹按任务难度做重采样，避免简单任务占满训练集

## 8.11 SFT 训练

### Step 20. 模型选择

先从 `7B-8B instruct base model` 开始，不要一开始就追求更大模型。

建议：

- 先做 LoRA/QLoRA
- 确认格式学习和物理修正能力成立后，再决定是否继续 full finetune

### Step 21. 训练配置

推荐起点：

- context length: `4096`
- effective batch size: `64`
- learning rate: `1e-4` 到 `2e-4`
- epochs: `2-3`
- warmup ratio: `0.03`
- LoRA rank: `32` 或 `64`
- precision: `bf16`

训练目标：

- 严格 mask 掉输入部分 loss
- 强化 JSON schema 合法性
- 对关键数值字段增加 format validation

### Step 22. 训练后评估

SFT 评估不能只看 loss，要看：

- JSON 合法率
- 首次命中率
- 修正成功率
- 平均 queries to success
- 对 OOD 任务的稳定性

## 8.12 可选第二阶段

如果 SFT 已经有效，可以加：

- verifier reward 下的离线 preference optimization
- rejection sampling finetuning
- 小规模 online refinement

但这不是首投 NeurIPS D&B 的必要条件。

## 9. benchmark 标签与分类体系

每个任务必须至少有以下标签：

- transduction type
- structure type
- material set
- geometry regime
- excitation type
- load model
- objective type
- primary constraint type
- source type: paper-grounded or synthetic
- split: train/val/test/ood

这样做的价值是：

- 方便做分桶评测
- 方便 reviewer 看到 benchmark 不是一锅粥

## 10. 最小可投稿版本

如果时间有限，先做到这个版本：

- 只做 piezoelectric cantilever
- 250 篇黄金论文
- 5,000 个公开任务
- verifier 经 FEM 和少量硬件校准
- 6 个强 baseline
- 1 个 distilled 8B
- 1 套公开复现实验脚本

这已经是能投 D&B 的形状。

## 11. 不要犯的致命错误

- 用“全栈很大”替代“问题定义清楚”
- 用 COMSOL 一致性替代真实世界验证
- benchmark 没有固定预算
- test 集和 teacher trace 泄漏
- verifier 太慢或不可解释
- 从非法来源大规模抓全文
- 论文里只讲 agent，benchmark 本身讲不清

## 12. 执行顺序

最优顺序不是先做 LLM，而是：

1. 定义范围和 JSON schema
2. 建立 OpenAlex/Semantic Scholar 检索脚本
3. 建立 PDF registry 和合规下载器
4. 做 PDF 解析和字段提取
5. 做 v1 verifier
6. 做 gold paper 筛选
7. 生成 benchmark task
8. 跑传统优化 baseline
9. 跑 zero-shot/RAG/verifier-guided LLM
10. 生成 teacher traces
11. 做 SFT
12. 做 FEM/hardware transfer
13. 整理 artifact
14. 最后再写论文

## 13. 建议的 24 周排期

### Week 1-3

- query 设计
- metadata 拉取
- 去重
- PDF registry

### Week 4-7

- PDF 解析
- 分类器
- 字段抽取
- JSON schema 稳定

### Week 8-10

- v1 verifier
- gold paper 物理一致性筛选

### Week 11-13

- benchmark 任务生成
- 数据切分
- baseline 协议定稿

### Week 14-16

- 传统优化方法跑通
- zero-shot 和 RAG baseline 跑通

### Week 17-19

- verifier-guided agent
- teacher trace 采样

### Week 20-21

- SFT
- distilled model 评测

### Week 22-23

- FEM 和硬件 transfer
- artifact 打包

### Week 24

- 论文写作
- mock review
- 只在过硬门槛时提交

## 14. 官方要求与外部依赖

### NeurIPS D&B

- D&B 是正式 NeurIPS track
- 2025 起强调数据与代码在投稿时可访问
- 推荐在 Dataverse、Kaggle、Hugging Face、OpenML 托管数据，并附 Croissant metadata

### OpenAlex

- 2026 年 2 月 13 日起 API key 必需
- 免费 key 有每日 credit 限制
- `best_oa_location` 和 content 下载可用于合法 OA PDF 获取

### Semantic Scholar

- 适合做 paper search、citation expansion、metadata completion
- 使用时要遵守其 API license 和公开归因要求

## 15. 参考入口

- NeurIPS D&B CFP: [https://neurips.cc/Conferences/2025/CallForDatasetsBenchmarks](https://neurips.cc/Conferences/2025/CallForDatasetsBenchmarks)
- NeurIPS Data Hosting Guidelines: [https://neurips.cc/Conferences/2025/DataHostingGuidelines](https://neurips.cc/Conferences/2025/DataHostingGuidelines)
- NeurIPS Reviewer Guidelines: [https://neurips.cc/Conferences/2025/ReviewerGuidelines](https://neurips.cc/Conferences/2025/ReviewerGuidelines)
- OpenAlex API Overview: [https://docs.openalex.org/how-to-use-the-api/api-overview](https://docs.openalex.org/how-to-use-the-api/api-overview)
- OpenAlex Rate Limits and Authentication: [https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication](https://docs.openalex.org/how-to-use-the-api/rate-limits-and-authentication)
- OpenAlex Works Filters: [https://docs.openalex.org/api-entities/works/filter-works](https://docs.openalex.org/api-entities/works/filter-works)
- OpenAlex Work Object: [https://docs.openalex.org/api-entities/works/work-object](https://docs.openalex.org/api-entities/works/work-object)
- OpenAlex Full-text PDFs: [https://docs.openalex.org/download-all-data/full-text-pdfs](https://docs.openalex.org/download-all-data/full-text-pdfs)
- OpenAlex CLI: [https://docs.openalex.org/download-all-data/openalex-cli](https://docs.openalex.org/download-all-data/openalex-cli)
- Semantic Scholar API Overview: [https://www.semanticscholar.org/product/api](https://www.semanticscholar.org/product/api)
- Semantic Scholar API Tutorial: [https://www.semanticscholar.org/product/api/tutorial](https://www.semanticscholar.org/product/api/tutorial)
- Semantic Scholar API License: [https://api.semanticscholar.org/license/](https://api.semanticscholar.org/license/)
