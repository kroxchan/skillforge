# SkillForge 开发日志

> 实时同步开发进展、决策记录、技术债务。所有开发决策都记录在此，PRD 更新后同步标注。

---

## 元信息

| 字段 | 内容 |
|------|------|
| 项目名 | SkillForge |
| 仓库 | `skillforge/` (在 digital-human/skills 下) |
| 许可证 | Apache 2.0 |
| 开发状态 | **Stage 0 ✅ Stage 1 ✅ Stage 2 ✅ Stage 3 ✅ Stage 4 ✅** |
| 最后更新 | 2026-04-16 |
| 当前版本 | v0.1.0-alpha |

---

## 目录

- [版本记录](#版本记录)
- [架构决策记录 (ADR)](#架构决策记录-adr)
- [待办事项](#待办事项)
- [已知技术债务](#已知技术债务)
- [学术对照表](#学术对照表)
- [设计改进记录](#设计改进记录)

---

## 版本记录

### v0.1.0-alpha (2026-04-15)

**状态**: Stage 0 ✅ Stage 1 ✅ Stage 2 ✅ Stage 3 ✅ Stage 4 ✅  |  Stage 5 待定

**已完成**:
- Stage 0: pyproject.toml + CLI 工具（analyze/search/list-skills/push/dashboard + 新增 `run` 命令）✅
- Stage 1 L1 轨迹写入（evaluator.py finalize 方法）✅
- Stage 1 L0 索引更新（indexer.py 移动平均）✅
- Stage 1 capability_gains 动态校准（registry.py update_effectiveness）✅
- Stage 1 engine.py `SkillForgeOrchestrator.run()` + `evaluate_and_close()` 串联 Phase 1-4 ✅
- Stage 2 CONTRIBUTING.md ✅
- Stage 2 observability tracing（tracing.py PhaseTiming + TimingLogger）✅
- Stage 2 sandbox 执行（executor.py `SandboxRunner`）✅
- 端到端测试（tests/test_skillforge.py）8/8 通过 ✅
- Stage 3: MAR 多角色辩论评估（mar.py）✅
- Stage 3: 向量语义检索 + 混合检索（vector_search.py）✅
- Stage 3: Orchestrator 串联调用链路（engine.py）✅
- Stage 3: 集成测试（tests/test_stage3_integration.py）13/13 通过 ✅
- Stage 4: Reflexion Memory 重试闭环（reflexion.py ReflectionLoader）✅
- Stage 4: Orchestrator 注入 L2 反思上下文到 Phase 1 ✅
- Stage 4: ReflexionLoader + evaluator 绝对路径对齐（修复 cwd 漂移）✅
- Stage 4: 集成测试（tests/test_stage4_integration.py）11/11 通过 ✅
- Stage 4: 单元测试（tests/test_reflexion.py）13/13 通过 ✅
- 修复：parse_reflections_file 支持 evaluator 写入的格式（task_type 后多空格）
- 修复：evaluator._memory_dir 绝对路径，L2 反思写到正确位置
- 新增：registry.py `list_skills()` 方法（供 HybridSkillMatcher 构建向量索引）
- 新增：models.py Phase4Result.mar_result 字段（Stage 3 MAR 结果）
- 新增：models.py Reflection.task_type 字段（Stage 4 L2 索引过滤）

**目录结构**:
```
SKILLFORGE/
├── pyproject.toml
├── README.md / PRD.md / SKILL.md / DEVLOG.md
├── config.yaml / skillforge-registry.yaml
├── memory/
│   ├── capability-index.yaml   ← L0 索引
│   └── reflections.md
├── src/skillforge/              ← Python 包
│   ├── __init__.py             ← 含 __version__ = "0.1.0"
│   ├── __main__.py             ← 支持 python -m skillforge
│   ├── models.py               ← 含 SkillForgeResult + Phase4Result.mar_result + Reflection.task_type ✅
│   ├── config.py               ← 含 Stage3Config + Stage4Config ✅
│   ├── indexer.py             ← 含 update_effectiveness ✅
│   ├── registry.py            ← 含 update_effectiveness + list_skills() ✅
│   ├── engine.py              ← 含 SkillForgeOrchestrator + Stage 3/4 串联 ✅
│   ├── decider.py             ← 含五态决策 ✅
│   ├── evaluator.py           ← 含 finalize + MAR 入口 + L2 反思写入 ✅
│   ├── executor.py            ← 含 SandboxRunner ✅
│   ├── forger.py / cli.py
│   ├── tracing.py             ← TimingLogger ✅
│   ├── mar.py                 ← MARCoordinator ✅（Stage 3）
│   ├── vector_search.py       ← HybridSkillMatcher ✅（Stage 3）
│   └── reflexion.py            ← ReflectionLoader ✅（Stage 4）
└── tests/
    ├── __init__.py
    ├── test_skillforge.py      ← 8 个测试 ✅
    ├── test_mar.py             ← 9 个测试 ✅（Stage 3）
    ├── test_vector_search.py   ← 10 个测试 ✅（Stage 3）
    ├── test_reflexion.py       ← 13 个测试 ✅（Stage 4）
    └── test_stage4_integration.py  ← 11 个测试 ✅（Stage 4）
```

**CLI 命令验证**:
```
$ python -m skillforge list-skills    ✅ 列出 5 个种子 skill
$ python -m skillforge search code    ✅ 搜索并展示 Code Expert Skill
$ python -m skillforge analyze "写 Python 爬虫"  ✅ 返回五态 + 候选列表
$ python -m skillforge dashboard      ✅ 显示 L0 索引统计
```

---

### v0.1.0-design (2026-04-15)

**状态**: 设计阶段初稿完成

**产出**:
- `PRD.md` — 产品需求文档
- `SKILL.md` — Agent 行为指南
- `config.yaml` — 全局配置
- `skillforge-registry.yaml` — 含 5 个种子 skill 的注册表
- `src/models.py` — Pydantic 数据模型
- `src/registry.py` — Skill Registry 管理
- `src/engine.py` — Phase 1 预判引擎
- `src/decider.py` — Phase 2 决策器
- `src/executor.py` — Phase 3 增强执行
- `src/evaluator.py` — Phase 4 质量评估
- `src/forger.py` — 自创建 skill 生成器
- `memory/reflections.md` — 空反思日志

**待完成**:
- CLI 工具
- 集成测试
- 文档站

---

### v0.1.0-alpha (2026-04-15)

**状态**: Stage 0 完成 ✅

**变更**:

- 重构目录结构：`src/` → `src/skillforge/`（Python 包结构）
- `src/skillforge/models.py` — 从 markdown 文档重写为真正的 Pydantic 类
- `src/skillforge/config.py` — 新增配置加载器
- `src/skillforge/indexer.py` — 新增 L0 Capability Index 管理器（三层 Progressive Disclosure 第一层）
- `src/skillforge/cli.py` — 新增 CLI 工具（analyze / search / list-skills / push / dashboard）
- `src/skillforge/__main__.py` — 新增，支持 `python -m skillforge`
- `pyproject.toml` — 新增，hatchling 构建配置，Apache 2.0 许可证
- `memory/capability-index.yaml` — 新增，L0 索引骨架
- 修复：`decider.py` 中文引号语法错误
- 修复：`registry.py` quality_tier 映射（L1/L2/L3）
- 修复：所有模块相对导入改为绝对导入

**CLI 命令验证**：

```
$ python -m skillforge list-skills    ✅ 列出 5 个种子 skill
$ python -m skillforge search code    ✅ 搜索并展示 Code Expert Skill
$ python -m skillforge analyze "写 Python 爬虫"  ✅ 返回五态 + 候选列表
$ python -m skillforge dashboard      ✅ 显示 L0 索引统计
```

**目录结构**：

```
SKILLFORGE/
├── pyproject.toml
├── README.md / PRD.md / SKILL.md / DEVLOG.md
├── config.yaml / skillforge-registry.yaml
├── memory/
│   ├── capability-index.yaml   ← 新增
│   └── reflections.md
└── src/
    └── skillforge/            ← 重构：Python 包
        ├── __init__.py
        ├── __main__.py        ← 新增
        ├── models.py          ← 重写
        ├── config.py          ← 新增
        ├── indexer.py         ← 新增
        ├── registry.py
        ├── engine.py
        ├── decider.py
        ├── evaluator.py
        ├── executor.py
        ├── forger.py
        └── cli.py             ← 新增
```

---

## 架构决策记录 (ADR)

### ADR-001: Phase 1 预判采用 CoT Prompt 而非 Hidden State 分类

**日期**: 2026-04-15
**状态**: 已决定

**背景**: CapBound 论文提出了两种预判路径：
- 黑盒：分析推理表达密度曲线（confident vs uncertain expressions 的时间分布）
- 白盒：hidden state 线性分类

**决策**: Stage 1-2 先实现 CoT prompt 方案（黑盒等效），白盒路径作为 Stage 5 的研究课题。

**理由**:
1. 不依赖特定模型（白盒需要能访问 hidden states 的模型）
2. 实现成本低，可快速验证概念
3. CoT prompt 方案本身已能覆盖 80% 场景

**影响**: Stage 5 应补充白盒预判路径的探索计划。

---

### ADR-002: Skill Registry 采用 YAML 持久化而非数据库

**日期**: 2026-04-15
**状态**: 已决定

**决策**: Registry 用 YAML 文件存储，不引入数据库依赖。

**理由**:
1. 符合"纯文本workspace"理念（与 OpenClaw 一脉相承）
2. 可 Git 版本控制，多人协作天然合并
3. 对 skill 作者来说可读可写，无学习成本
4. 项目级 Registry 可覆盖全局 Registry（合并策略）

**替代方案**: 未来可引入 SQLite 作为可选存储，用于大数据量场景。

---

### ADR-003: capability_gains 采用静态手动填写 + 动态校准

**日期**: 2026-04-15
**状态**: 已决定

**决策**: 新 skill 的 `capability_gains` 由作者手动填写；使用过程中 Phase 4 反馈持续校准（移动平均更新 `avg_effectiveness`）。

**理由**:
1. 冷启动问题：没有历史数据时无法自动推断
2. 透明性：作者声明的 gains 是有意的设计决策
3. 闭环校准：真实使用数据会修正偏差

**待办**: 设计 `update_effectiveness` 算法，确保移动平均不收敛到极端值。

---

### ADR-004: 自创建 Skill 必须经过用户审核才能入库

**日期**: 2026-04-15
**状态**: 已决定

**决策**: SkillForge-Forger 生成的草稿必须用户审核确认，才能写入正式 Registry。

**理由**:
1. 避免低质量 skill 污染 Registry
2. 用户对工作区有控制权，不会被"悄悄添加的 skill"干扰
3. 审核过程本身是用户学习 skill 的机会

---

### ADR-005: Gap 分级从 3 档扩展到 5 态（借鉴 KnowSelf）

**日期**: 2026-04-15
**状态**: PRD 已更新，开发代码待更新

**决策**: 将 L1/L2/L3 三档扩展为五态：

| 态 | 条件 | Agent 行为 |
|----|------|-----------|
| **独立** | Gap < 5 | 直接执行，不记录 |
| **轻提示** | 5 ≤ Gap < 15 | 执行，结束时轻描淡写"有优化空间" |
| **建议增强** | 15 ≤ Gap < 30 | 输出结果 + 询问"是否启用 skill" |
| **强制增强** | 30 ≤ Gap < 50 | 主动建议 skill，用户确认后才执行 |
| **超边界** | Gap ≥ 50 | 坦白说"我可能做不好，建议你找专业人士/换模型" |

**理由**: KnowSelf 的研究表明，agent 在"独立完成"和"必须求助"之间存在更细粒度的情境判断。当前三档过于粗放，强制增强和超边界混在一起会让用户困惑。

**影响**: `src/decider.py` 和 `config.yaml` 的阈值需要对应更新。

---

## 待办事项

### 优先级 P0（开源最小可用集）

- [x] 设计 CLI 工具（`push` / `pull` / `search` / `list` / `eval` / `run`）— `src/skillforge/cli.py` ✅
- [x] 添加 `pyproject.toml`，支持 `pip install skillforge` ✅
- [x] 补充 `__init__.py` 版本信息 ✅
- [x] 更新 `src/decider.py` 支持五态决策（ADR-005）✅
- [x] 更新 `config.yaml` 阈值（ADR-005）✅
- [x] L1 轨迹写入（`evaluator.py finalize` 方法）✅
- [x] L0 索引更新（`indexer.py 移动平均更新 capability-index.yaml`）✅
- [x] 添加集成测试（`tests/test_skillforge.py`）✅
- [x] `src/engine.py` — `SkillForgeOrchestrator.run()` + `evaluate_and_close()` 串联 Phase 1-4 ✅

### 优先级 P1（完整工程化）

- [x] capability_gains 动态校准算法（`registry.py update_effectiveness`）✅
- [x] CONTRIBUTING.md（开源必需）✅
- [x] observability tracing（`tracing.py TimingLogger`，写入 `memory/timings.yaml`）✅
- [x] sandbox 执行支持（`executor.py SandboxRunner`，代码类任务自动验证）✅
- [ ] Skill 语义版本策略（`v1.0.0` / `v1.1.0` / `v2.0.0`）

### 优先级 P2（多 Agent 协作）

- [x] Multi-Critic 评估（MAR 机制）✅
- [x] 向量语义检索（HybridSkillMatcher + ChromaDB/Mock）✅
- [x] Orchestrator 串联调用链路✅
- [x] Reflexion memory 重试闭环（Stage 4 ReflectionLoader）✅
- [ ] 规划 Agent + 执行 Agent + 审查 Agent 分工设计

### 优先级 P3（高级功能）

- [x] 向量语义检索（ChromaDB 集成）✅（Stage 3 Mock 实现）
- [ ] 白盒预判路径（CapBound hidden state 分类）
- [ ] webhook 通知（skill 审核通过、执行失败等）
- [ ] Web UI（skill 发现 + 管理）

---

## 已知技术债务

| # | 项目 | 描述 | 计划解决阶段 |
|---|------|------|------------|
| TD-001 | capability_gains 静态 | 新 skill 的 gains 靠作者手动填，没有自动推断机制 | P1 |
| TD-002 | 无 sandbox | 代码类任务的 Phase 4 评估只能靠用户评分，无法自动执行验证 | P1 |
| TD-003 | 无 observability | Phase 1-4 各阶段没有耗时追踪，无法分析性能瓶颈 | P1 |
| TD-004 | YAML Registry 性能 | skill 数量 >1000 时全文扫描效率低 | P2（迁移到 SQLite 可选方案） |
| TD-005 | 多 Agent 协作 | 单 Agent 自评存在确认偏误风险，MAR 机制未实现 | P2 ✅ 已完成 |
| TD-006 | 白盒预判 | CapBound hidden state 路径未实现 | P3 |

---

## 学术对照表

| 论文/项目 | 发表 | 核心贡献 | 我们对应实现 | 对照说明 |
|---------|------|---------|------------|---------|
| KnowSelf (ACL 2025) | ACL 2025 | Situational self-awareness，特殊 token 三态切换 | Phase 1 Gap 分析 + 五态决策 | 我们借鉴了情境判断思想，但用 Gap 分级替代了 KnowSelf 的 special token 训练方案，实现成本更低 |
| CapBound (清华 & 蚂蚁) | arXiv | Hidden states 线性可分，推理表达密度曲线 | Phase 1 能力预判 | 我们的 CoT prompt 方案等效于 CapBound 的黑盒路径，白盒路径作为 Stage 5 研究课题 |
| Reflexion (NeurIPS 2023) | NeurIPS 2023 | verbal reinforcement learning，episodic memory | Phase 4 反思记录 + `memory/reflections.md` + Stage 4 ReflectionLoader 闭环 | 基本一致，Stage 4 实现了"下次同类任务自动加载反思"的完整闭环 |
| MAR (Ozer et al.) | ? | Multi-agent critic辩论，解决确认偏误 | Phase 4 MARCoordinator.evaluate() | Stage 3 已实现，单次调用三角色+Judge |
| Hermes Agent | 开源 | 失败后自动生成 SKILL.md | SkillForge-Forger | 模式一致，草稿质量控制需细化 |
| CAMEL | 开源 | 16k stars，多 Agent 协作框架 | 多 Agent 协作 | 参考其 agent 架构和 observability 设计 |
| SkillHub (科大讯飞) | 开源 | 企业级 skill 注册表，RBAC + 审核流 | Registry 设计 | 参考其 governance 机制（审核流程、namespace） |
| AgentSkills Registry | 开源 | npm-style CLI-first skill 格式 | SKILL.md 格式 | 基本一致，需补充语义版本和 namespace |

---

## 设计改进记录

### 2026-04-15: 启动方式决策（ADR-006）

**问题**: SkillForge 是"每次 Agent 启动注入一次"还是"每次任务调用都触发"？

**决策**: 后者，但以静默方式运行。Agent 收到 SKILL.md 引导原则后，每次任务执行都自动在内部跑 Phase 1-4 循环，用户感知不到 overhead。SKILL.md 只在 Agent 初始化时注入一次，之后由 Agent 自觉执行四 Phase，不重复塞入 prompt。

**理由**: SkillForge 是行为模式，不是重复指令。

---

### 2026-04-15: 记忆索引三层设计（ADR-007）

**问题**: 记忆机制如何避免 token 膨胀？

**参考**: SkillReducer (2025) 发现 skill body 中 60% 是非行动内容，压缩 39% 后功能质量提升 2.8%（less-is-more）。SkillRouter (2025) 发现 full-text 是关键路由信号，但不能全量注入。

**决策**: 采用三层 Progressive Disclosure 索引：

- L0 `capability-index.yaml`（<500 tokens）：Agent 启动时注入。task_type → (count, avg_delta, trend, gap_adjustment)。Phase 1 直接读取。
- L1 执行记录（<1K tokens）：Phase 2 决策前按 task_type 加载。只读当前类型的历史，不遍历全量。
- L2 反思日志（<2K tokens）：Phase 4 评估前读取，不注入 prompt。

**总 token 预算**: <3.5K tokens/次，远低于 SkillReducer 报告的平均 skill body（10K+ tokens）。

**设计依据**: Meta-Policy Reflexion (2025) 的 Meta-Policy Memory 思路——将 episodic reflections 提取为 predicate-like rules，减少冗余；SkillReducer 的 tiered architecture——核心规则常驻，补充内容按需加载。

---

### 2026-04-15: Gap 五态设计（KnowSelf 启发）

**改进前**（PRD 初稿）:
- L1: Gap < 10，直接执行
- L2: 10 ≤ Gap < 25，建议增强
- L3: Gap ≥ 25，强制增强

**改进后**（KnowSelf 启发）:
- 独立: Gap < 5
- 轻提示: 5 ≤ Gap < 15
- 建议增强: 15 ≤ Gap < 30
- 强制增强: 30 ≤ Gap < 50
- 超边界: Gap ≥ 50

**改动原因**: KnowSelf 证明 agent 在"完全独立"和"必须求助"之间存在更细粒度的情境判断。三档设计过于粗放，把"边界模糊但可能做得不错"和"明显超出能力"混在同一档。

**影响范围**: PRD.md, src/decider.py, config.yaml

### 2026-04-15: CLI-first 设计决策

**决策**: 开源版必须提供 CLI，优先级 P0。

**参考**: AgentSkills Registry 的 `agentskills` CLI，CAMEL 的 `camel-cli`，SkillHub 的 REST API。

**待设计命令**:
```
skillforge analyze "任务描述"           # Phase 1 预判
skillforge search "关键词"              # 搜索 Registry
skillforge list                        # 列出所有 skill
skillforge push ./my-skill              # 上传 skill
skillforge pull skill-id               # 下载 skill
skillforge eval task-file.json          # 批量评估
skillforge dashboard                   # 查看统计
```
