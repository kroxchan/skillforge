# SkillForge 开发日志

> 实时同步开发进展、决策记录、技术债务。版本按时间正序排列（旧 → 新）。以后每次新增版本**追加到文档末尾**（在 ADR / 技术债务 / 反思章节**之前**）。

---

## 元信息

| 字段 | 内容 |
|------|------|
| 项目名 | SkillForge |
| 仓库 | https://github.com/kroxchan/skillforge |
| 许可证 | Apache 2.0 |
| 当前版本 | **v0.2.9-review** — 进入纯使用模式，等真实数据积累后再 review |
| 测试基线 | **159 passed** |
| 最后更新 | 2026-04-17 |

---

## 版本记录格式模板（以后更新沿用）

每个版本块严格遵循以下结构，按时间正序追加到 [版本记录](#版本记录) 章节末尾：

```markdown
### vX.Y.Z (YYYY-MM-DD) — <一句话标题>

**状态**: <完成 | 复审中 | 进行中> | 测试 <N/N passed>
**触发**: <为什么做这个版本（用户反馈 / 复审发现 / 新功能需求）>

#### 核心变更
- <bullet，聚焦"做了什么"，不展开细节>
- ...

#### FIX 执行记录（可选）
| ID | 优先级 | 状态 | 文件 | 描述 |
|----|-------|------|------|------|
| FIX-XXX | P0 | ✅ | path | ... |

#### 验证（可选）
- <关键 pytest / 手工验证记录>

#### 设计洞察 / 决策（可选）
<一两段总结，为未来留下决策轨迹>

---
```

**精简原则**：
- 每个版本块目标 30~80 行，超长内容移到 [架构决策记录](#架构决策记录-adr) 或 [技术债务](#已知技术债务)
- "复审（review）"结论若导致了实际修复，合并到下一个版本号里；review 本身单独一节只保留战略结论
- FIX 记录保留 ID + 一句话，细节放代码提交和 reflections.md

---

## 目录

- [版本记录](#版本记录)
  - [v0.1.0-design (2026-04-15)](#v010-design-2026-04-15--设计初稿)
  - [v0.1.0-alpha (2026-04-15)](#v010-alpha-2026-04-15--stage-0-4-python-引擎完成)
  - [v0.1.0-audit (2026-04-17)](#v010-audit-2026-04-17--全盘审计)
  - [v0.1.1 (2026-04-17)](#v011-2026-04-17--审计修复批次)
  - [v0.1.2 (2026-04-17)](#v012-2026-04-17--actualdelta-解耦)
  - [v0.2.0 (2026-04-17)](#v020-2026-04-17--mdc-权威化--3-维统一)
  - [v0.2.1 (2026-04-17)](#v021-2026-04-17--p0-闭环打通)
  - [v0.2.2 (2026-04-17)](#v022-2026-04-17--phase-4-默认基线化)
  - [v0.2.3 (2026-04-17)](#v023-2026-04-17--sf-update-l0-helper--registry-去重)
  - [v0.2.4 (2026-04-17)](#v024-2026-04-17--第三轮复审--漏洞清扫)
  - [v0.2.5 (2026-04-17)](#v025-2026-04-17--phase-23-强制契约)
  - [v0.2.6 (2026-04-17)](#v026-2026-04-17--涌现式-registry)
  - [v0.2.7 (2026-04-17)](#v027-2026-04-17--涌现一致性扫荡)
  - [v0.2.8 (2026-04-17)](#v028-2026-04-17--cwd-独立性修复)
  - [v0.2.9-review (2026-04-17)](#v029-review-2026-04-17--复审回报递减拐点--进入纯使用模式)
- [架构决策记录 (ADR)](#架构决策记录-adr)
- [已知技术债务](#已知技术债务)
- [反思记录](#反思记录)
- [学术对照表](#学术对照表)

---

## 版本记录

### v0.1.0-design (2026-04-15) — 设计初稿

**状态**: 设计阶段完成

#### 核心变更
- 产出 PRD.md / SKILL.md / config.yaml / skillforge-registry.yaml
- 数据模型定义：`src/models.py`（Pydantic）
- 五个核心模块骨架：`registry.py` / `engine.py` / `decider.py` / `executor.py` / `evaluator.py` / `forger.py`
- Registry 预置 5 个种子 skill（`code-expert` / `research-skill` / `seo-analysis-skill` / `data-analysis-skill` / `video-production-skill`）

#### 待完成（推进到 v0.1.0-alpha）
- CLI 工具
- 集成测试
- 文档站

---

### v0.1.0-alpha (2026-04-15) — Stage 0~4 Python 引擎完成

**状态**: Stage 0~4 全部就绪 | 测试基线 51/51 passed

#### 核心变更
- **Stage 0**：`pyproject.toml` + CLI（`analyze` / `search` / `list-skills` / `push` / `dashboard` / `run`）+ 包结构迁移到 `src/skillforge/`
- **Stage 1**：Phase 1-4 串联 · L0/L1/L2 记忆 · 移动平均校准（`engine.py::SkillForgeOrchestrator.run()` + `evaluate_and_close()`）
- **Stage 2**：observability tracing（`tracing.py::TimingLogger`）+ sandbox 执行（`executor.py::SandboxRunner`）
- **Stage 3**：MAR 多角色辩论（`mar.py`）+ 向量语义检索（`vector_search.py::HybridSkillMatcher`）
- **Stage 4**：Reflexion Memory 重试闭环（`reflexion.py::ReflectionLoader`）+ L2 反思自动注入 Phase 1

#### 测试
- `test_skillforge.py` (8) · `test_mar.py` (9) · `test_vector_search.py` (10) · `test_reflexion.py` (13) · `test_stage4_integration.py` (11) = **51 passing**

---

### v0.1.0-audit (2026-04-17) — 全盘审计

**状态**: 审计完成 | 71/71 passed（新增 test_stage3_integration 13 个测试）
**触发**: 上线前自检发现系统性架构问题

#### 关键发现
- **两套系统未对齐**：Python Engine 与 `integrations/skillforge.mdc` 的 Phase 1 维度（6 维 vs 3 维）互相冲突
- **capability_gains 全 0**：Registry 中 5 个种子 skill 的预估增益未填写，Phase 2 决策无实际依据
- **Phase 4 链路断裂**：`gap_adjustment` 从未被 Phase 1 读取使用
- **六维自评方法论脆弱**：LLM 被要求量化 6 个自评维度，无锚定 / 无校验，结果可造假

→ 修复方案延后到 v0.1.1 批次执行。

---

### v0.1.1 (2026-04-17) — 审计修复批次

**状态**: BUG-001/002/003/005/006/009/010/011 已修复 | 71/71 passed

#### FIX 执行记录
| ID | 级别 | 状态 | 文件 | 描述 |
|----|------|------|------|------|
| BUG-001 | 🔴 Critical | ✅ | `cli.py` | 新增 `eval`（Bridge 主路径）+ `ingest`（降级路径）命令 |
| BUG-002 | 🔴 Critical | ✅ | `executor.py` | 新增 `_synthesize_minimal_skill_card`，path 缺失时合成最小卡片 |
| BUG-003 | 🔴 Critical | ✅ | `evaluator.py:165` | `Path("memory")` → `self._memory_dir`，路径对齐 |
| BUG-005 | 🟠 High | ✅ | `integrations/skillforge.mdc` | 六维 → 三维；SF 标签简化为 `[SF | Gap≈X | state]` |
| BUG-006 | 🟡 Medium | ✅ | `config.yaml` | `forger_trigger: 3 → 8`，防止小样本过拟合（v0.2 又改回 5） |
| BUG-009 | 🟢 Low | ✅ | `indexer.py` | 删除重复 `_init_defaults` |
| BUG-010 | 🟢 Low | ✅ | `indexer.py` | Pydantic V2 迁移：`class Config` → `model_config = ConfigDict(...)` |
| BUG-011 | 🟢 Low | ✅ | `executor.py` | 删除 `SandboxRunner` 中冗余变量 |

#### 设计决策
- **虚拟 Skill 机制（ADR-008）**：Registry 条目不再强制物理 SKILL.md，可合成 100~150 tokens 最小卡片注入
- **双路 Bridge（ADR-009）**：Phase 4 末尾调 `sf eval` 实时写；降级走 `cursor-timings.md` → `sf ingest` 批量导入

---

### v0.1.2 (2026-04-17) — actual/delta 解耦

**状态**: BUID-001 修复完成 | 71/71 passed

#### 问题
1. `actual = predicted + (rating-3)*20` → 同一 rating 对不同 predicted 产生不同 actual，跨任务 delta 不可比
2. `indexer.update()` 内用 `delta = actual - predicted` → 当 `actual=predicted` 时 delta 永远为 0

#### 核心变更
- `Phase4Result` 新增独立 `delta` 字段
- `evaluator.evaluate()` 改为 `actual=predicted`，`delta=(rating-3)*20` 从源头算
- `indexer.update()` 新增 `delta` 参数，移除内部推导
- `engine.evaluate_and_close()` 去掉废弃参数（actual_score / llm_self_rating / tool_verification）
- 删除 `_compute_score` 死代码及配套 weight 字段

#### 最终评分约定
```
actual = predicted（质量以预估为准）
delta  = (user_rating - 3) * 20
  rating=5 → +40（超预期，罕见）
  rating=3 → 0  （符合预期，默认基线）
  rating=1 → -40（低于预期）
```

---

### v0.2.0 (2026-04-17) — mdc 权威化 + 3 维统一

**状态**: 全链路跑通 | 71/71 passed

#### 核心变更
- **mdc 定为最权威版本**：Cursor 场景以 `.cursor/rules/skillforge.mdc` 为准，`engine.py` 顶部加 DEPRECATED NOTICE
- **维度统一为 3 维**：`prec` / `reas` / `tool`，PRD / SKILL.md / engine.py / registry / mdc 全部对齐
- **Phase 4 真实跑通**：Agent 用户打分 → 直接写 `cursor-timings.md`，不依赖外部命令
- **capability_gains 不填假数据**：积累 ≥10 条真实反馈前置 0，由 Phase 4 校准

#### FIX 执行记录（精简）
| ID | 文件 | 描述 |
|----|------|------|
| AUDIT-001~003 | `skillforge.mdc` | Phase 4 写 `cursor-timings.md` / 反思格式同步 / Phase 1 读 `gap_adjustment` |
| AUDIT-004~007 | `engine.py` / `models.py` | Phase 1 Prompt 6 维 → 3 维；五态常量对齐；`Phase1Result.gap_level` 改五态字符串 |
| AUDIT-008 | `cli.py` | `_parse_cursor_timings` 支持新表格格式 |
| AUDIT-009 | `skillforge-registry.yaml` | capability_gains 3 维 + quality_tier 改 unknown |
| AUDIT-010~011 | `config.yaml` / `config.py` | 删死字段（calibration_enabled / default_weight / output） |
| AUDIT-012~013 | `PRD.md` / `SKILL.md` | 添加权威版本说明，Section 编号调整 |

---

### v0.2.1 (2026-04-17) — P0 闭环打通

**状态**: 审查完成 + P0 修复执行完成

#### 复审背景
对 SkillForge 全盘检查（28 个文件），发现整体处于"骨架有了、血肉不足"阶段——代码量充足（24 文件 + 71 测试），但核心自改进闭环从未真正跑通：
- L0 索引 0 条数据
- Registry capability_gains 全为 0
- Forger 从未触发

#### 核心变更
- Phase 2/3 初版契约引入（v0.2.5 升级为强制契约）
- 填充 5 个种子 skill 的 `capability_gains` 预估值（标注"预估，待验证"）
- mdc 3 维统一到用户级 `/Users/vivx/.cursor/rules/skillforge.mdc`
- `integrations/skillforge.mdc` 移至 `docs/archive/ARCHIVE-v0.1.1-6dims.mdc`

#### 设计洞察
> "骨架有了，血肉不足——SkillForge 真正需要的不是更多功能，而是真实使用验证期。"
>
> 这个判断在之后的 8 个版本里反复被验证。

---

### v0.2.2 (2026-04-17) — Phase 4 默认基线化

**状态**: 用户首次真实反馈驱动的修正

#### 用户反馈
> "只要用户不回复说你做错了或者要改进什么的，一般就是 3。我觉得很少会有 5 的情况。一般就是 3 和 1，直接让用户在窗口回 1、3、5 确实感觉太奇怪了。"

这是 SkillForge 上线后的**第一条真实用户反馈**。命中两个设计缺陷：主动询问本身违背"Phase 4 透明"初衷，以及 3/5 对称假设不成立。

#### 核心变更
| ID | 状态 | 文件 | 描述 |
|----|------|------|------|
| FIX-009 | ✅ | `skillforge.mdc` | Phase 4 默认 `rating=3`；明确禁止主动询问 / 暴露自评 |
| FIX-010 | ✅ | `skillforge.mdc` | rating=5 标注"罕见"，触发条件收紧为明确惊喜 |
| FIX-011 | ✅ | `~/.cursor/rules/skillforge.mdc` | 同步用户级规则 |
| FIX-012 | ✅ | `SKILL.md` / `PRD.md` | Phase 4 章节同步 |
| FIX-013 | ✅ | `memory/capability-index.yaml` | 首次真实数据写入（`refactoring` count=1） |

#### 设计洞察
**"默认 3" 比 "无反馈跳过" 更符合长期学习的统计直觉**——默认 3 让 count 正确统计，delta=0 不扰动 `gap_adjustment`，只是把统计样本做满。

这次修复本身验证了 SkillForge 的价值：**真实用户反馈让设计错误浮出水面**。

---

### v0.2.3 (2026-04-17) — sf update-l0 helper + Registry 去重

**状态**: 第二轮复审 + 修复完成

#### 核心变更
- **`sf update-l0` CLI helper**（FIX-022）：text-level patch 保留注释 + 原子写入（tmp → rename）
- **Registry 成为 task_type 单一数据源**（FIX-015）：`indexer` 从 Registry 动态加载 `task_types`
- **Registry 去重**（FIX-017）：审查中发现每个 skill 在 Registry 中有两份（L2 版 + unknown 版），v0.2.1 FIX-005 填充时漏清理

#### FIX 执行记录
| ID | 优先级 | 状态 | 描述 |
|----|-------|------|------|
| FIX-014 | P0 | ✅ | 清理 `PHASE1_PROMPT_TEMPLATE` 6 维残留 |
| FIX-015 | P0 | ✅ | `indexer` 从 Registry 动态加载 task_types（单一数据源）|
| FIX-016 | P1 | ✅ | 简化 outcome 三分支为二分支 |
| FIX-017 | P1 | ✅ | Registry quality_tier 注释统一 + 去重 |
| FIX-018 | P2 | ✅ | `capability-index.yaml` 按字母序重排 |
| FIX-019 | P2 | ✅ | `docs/quickstart.md` 同步 `sf update-l0` |
| FIX-020 | P2 | ✅ | mdc 反思模板加"禁止外部归因"约束 |
| FIX-021 | P1 | ✅ | mdc 增加灰色反馈兜底（默认 `rating=3`） |
| FIX-022 | P0 | ✅ | 实现 `sf update-l0`（text-level patch + 原子写入） |

#### 改进亮点
1. **文本级 patch 保留注释**：Phase 4 不再走 `save()` 全量重写，regex 精确 patch，所有原有注释（含历史审计）保留
2. **原子写入**：tmp 文件 → rename，防写中断损坏
3. **CLI 简写 `sf`**：`sf update-l0 --task-type X --rating 3 --task-desc "..." --predicted 88` 一行完成
4. **反思质量锚定**（FIX-020）：模板明确禁止"任务描述不清 / 模型能力不足 / 工具不够"等外部归因，强制从三内因维度找根因

---

### v0.2.4 (2026-04-17) — 第三轮复审 + 漏洞清扫

**状态**: 复审 + 修复完成（FIX-023~038 批次）

#### 复审背景
用户第三次要求"全盘检查 + 实用性评估"。前两轮修完立即暴露新问题，本轮直面元问题：**这个系统真的值得继续投入吗？**

#### 核心发现 + 修复
| ID | 优先级 | 文件 | 描述 |
|----|-------|------|------|
| FIX-023 | P0 | `indexer.py::update_l0_file` | 补 `trend` + `global_gap_adjustment` 更新（之前永不触发）|
| FIX-024 | P0 | `tests/test_update_l0.py` (新) | 新增 26 项回归测试 |
| FIX-025~035 | P1 | 多文件 | mdc 行文权重 / evaluator 死代码分支 / `sf` 命令文档对齐 |
| FIX-036 | P0 | `cli.py` | `sf run --rating` 删除错误的 `actual_score` 参数（隐式 TypeError） |
| FIX-037 | P0 | 多文件 | 8 处硬编码 `task_type="other"` → `"default"`（避免污染 L0）|
| FIX-038 | P0 | `skillforge.mdc` | "数据存储"章节重写，明确 `sf update-l0` 是写入唯一入口 |

#### 设计洞察
**"骨架骨架骨架"**：Phase 2/3 此时仍是纸面概念，Registry 登记的 5 个种子 skill 的 `path` 字段全部指向物理不存在的文件。这成为 v0.2.5 "让 Phase 2/3 真正跑起来"的直接动机。

---

### v0.2.5 (2026-04-17) — Phase 2/3 强制契约

**状态**: 实施完成 | 110/110 passed（+9 新测试）

#### 核心变更
- **新增 `sf show <skill_id>` CLI**（FIX-039）：
  - `skill.path` 指向真实 SKILL.md → 输出完整文件（`source=skill_md`）
  - 不存在 → 用 Registry 的 description / task_types / capability_gains 拼 inline context（`source=registry_inline`，`path_missing=True`）
  - 支持 `--json` 供 Agent 自动化消费
- **mdc Phase 2 升级为强制契约**：Gap ≥ 15 时**必须**跑 `sf search`，必须展示候选表
- **mdc Phase 3 升级为强制契约**：用户确认后**必须**跑 `sf show`，回复末尾声明 source，path_missing 时主动坦白
- **辅助函数 `_build_inline_skill_context(skill)`**：标准化 Markdown fallback，空字段降级"（未指定）"

#### 后续承接
为 5 个种子 skill 补真实 SKILL.md，把 `source: registry_inline` 降到 0 —— 但该承接后被 v0.2.6 的涌现式范式取代（见下）。

#### 搁置事项（后续在 v0.2.7 批处理）
- FIX-040 SF 标签示例与 "max 定义" 不自洽
- FIX-041 mdc "反思记录"章节冗余
- FIX-042 `_infer_task_type` 首次匹配不稳定

---

### v0.2.6 (2026-04-17) — 涌现式 Registry

**状态**: 实施完成 | 119/119 passed（+13 新测试）

#### 范式转变的动机
用户反馈：
> "挑选种子 skill 是一件很重要的事情。但对于不同工作类型的人来说，他们的种子 skill 也不一样，倒不如让 agent 自己发现需要 skill 的时候自己去发掘吧，我们强行添加种子 skill，似乎意义不大。"

触发**设计范式回归**：skill 不是架构师设计的，而是 Agent 在真实工作中"长出来"的。

#### 决策参数（用户选择）
| 问题 | 决策 |
|------|------|
| Q1: 触发 Forger 的条件 | **A** — `count ≥ 5` |
| Q2: 生成草稿的质量层次 | **A** — 轻量骨架（只列事实，不替用户总结） |
| Q3: 保留还是清空已有 L0 数据 | **A** — 保留 |

#### 核心变更
- **清空 Registry `skills:`**（原 5 个种子全部移除）
- **Forger 从"paper concept"变为可工作模块**：`should_forge(task_type, ...)` + `forge_draft(task_type, ..., force)` 生成 `memory/self-made/<task>-draft-<date>.md`
- **`update_l0_file` 集成 Forger 自动触发**：达到阈值时返回 `forger_draft_path`，mdc 规则据此给用户一次性提示
- **新增 CLI**：`sf forge`（手动触发）/ `sf demand-queue`（查进度面板）
- **新增 `tests/test_forger_emergent.py`**（13 测试）

#### 设计决策：草稿为何是"轻量骨架"
Forger 不替用户总结"最佳实践"。它只列**事实**（task_type 执行了多少次 / rating 分布 / 最近 5 条审计摘要），由用户在此基础上写 Workflow / Trigger Conditions / Known Limitations。避免 AI 幻觉污染草稿内容。

---

### v0.2.7 (2026-04-17) — 涌现一致性扫荡

**状态**: 实施完成 | 151/151 passed（+32 新测试，`_infer_task_type` 专项）

#### 复审动机
v0.2.6 完成了涌现式 Registry 的结构性重构，但**只改了 Forger / Registry / Phase 2 三处**。Phase 4 的 task_type 消化逻辑、L0 索引结构、mdc 降级路径 / 反思章节 / 数据存储章节等多处仍然沿用 v0.2.5 前"预设种子"哲学下写的代码和文档。本轮做一次彻底的**哲学一致性扫荡**。

#### FIX 执行记录
| ID | 优先级 | 状态 | 文件 | 描述 |
|----|-------|------|------|------|
| FIX-049 | P0 | ✅ | `memory/capability-index.yaml` | 清理 legacy 条目，只保留 `default` + 实际活跃条目 |
| FIX-050 | P0 | ✅ | `skillforge.mdc` | Phase 4 task_type 选择规则重写（允许 Agent 自行命名 snake_case） |
| FIX-051 | P0 | ✅ | `skillforge.mdc` | 删除 StrReplace 降级路径（"严禁直接改 yaml"） |
| FIX-052 | P1 | ✅ | `skillforge.mdc` | 删除冗余"反思记录"章节 |
| FIX-053 | P1 | ✅ | `skillforge.mdc` | SF 标签示例注释对齐 "最大维度 = N" 逻辑 |
| FIX-054 | P1 | ✅ | `cli.py::sf forge` | 过滤 count=0 条目 + 无可触发时友好提示 |
| FIX-055 | P1 | ✅ | `cli.py::_infer_task_type` | 添加 docstring 标注"仅供 Python 引擎批量路径" |
| FIX-056 | P1 | ✅ | `indexer.py::DEFAULT_TASK_TYPES` | 注释更新（Registry 空时默认 `["default"]`）|
| FIX-057 | P2 | ✅ | `forger.py` | 草稿默认 `capability_gains` 从 0 改为 10（Phase 2 可见）|
| FIX-042 | P1 | ✅ | `cli.py::_infer_task_type` | 改 first-match 为 score-based；新增 `tests/test_infer_task_type.py` (32 测试)|

---

### v0.2.8 (2026-04-17) — CWD 独立性修复

**状态**: 实施完成 | 159/159 passed（+8 新测试）
**触发**: 第六轮复审发现 Cursor 路径 Phase 4 **实际从未真正工作过**的运行时根因

#### 核心发现（前 5 轮均漏掉）
```bash
$ cd /tmp && sf demand-queue
L0 索引不存在: memory/capability-index.yaml
```

`sf` 所有命令在非 SKILLFORGE 目录下 100% 失败。但 Cursor Agent 的 CWD 通常是**用户工作区**（如 `/Users/xxx/projects/foo`），不是 SKILLFORGE 根 —— 这就是为什么 Phase 4 执行率估计 < 10% 的根因。

**为什么前 5 轮漏掉**：所有测试都在 SKILLFORGE 项目根跑，相对路径"巧合生效"造成盲区。

#### FIX 执行记录
| ID | 优先级 | 状态 | 文件 | 描述 |
|----|-------|------|------|------|
| **FIX-058** | **P0** | ✅ | `config.py` | **根因修复**：`_find_project_root()` 新增 `__file__` fallback；`Config.load()` 绝对化 `memory_dir` / `registry_path` |
| FIX-058b | P0 | ✅ | `indexer.py` | `_find_registry_path()` 同步 `__file__` fallback |
| FIX-059 | P0 | ✅ | `skillforge.mdc` | Phase 4 新增"触发时机"契约（先 Phase 4 → 再 Phase 1）|
| FIX-060 | P0 | ✅ | `skillforge.mdc` | 尾部注释"严禁 StrReplace"，消除与 line 258 矛盾 |
| FIX-061 | P0 | ✅ | `skillforge.mdc` | 安装指令改用 `importlib.util.find_spec`，去掉 `find ~` 全盘扫描 |
| FIX-062 | P1 | ✅ | `skillforge.mdc` | Phase 2 情况 A 置首位扩写，情况 B 标注"未来态" |
| FIX-063 | P1 | ✅ | `cli.py::sf search` | 同时扫描 `memory/self-made/` 草稿 |
| FIX-064 | P1 | ✅ | `skillforge.mdc` | `trajectories/` 注释明确 Cursor 对话路径不产出 |
| FIX-065 | P2 | ✅ | `skillforge.mdc` | 新增"日常命令速查"节 |
| FIX-066 | P2 | ✅ | `indexer.py` + `cli.py` | `DEFAULT_TASK_TYPE` 常量化 |
| FIX-067 | P2 | ✅ | `tests/test_cwd_independence.py` (新) | 8 项集成测试，`foreign_cwd` fixture 切 `/tmp` |

#### 验证
- `cd /tmp && sf demand-queue` → 正常输出 task_type 表
- `cd /tmp && sf search "code"` / `sf list-skills` / `sf forge` → 全部正常
- `python3 -m pytest tests/ -q` → **159 passed**
- user-level mdc 已同步

#### 设计洞察（方法论教训）
下次复审必须至少包含一次"**在陌生环境执行**"的冒烟测试。"测试环境 = 生产环境"的假象让我们盲了 5 轮。

---

### v0.2.9-review (2026-04-17) — 复审回报递减拐点 / 进入纯使用模式

**状态**: 第七轮复审完成；**决定进入"纯使用模式"**；无代码变更
**触发**: 用户第七次要求"全盘检查 + 实用性评估"

#### 关键结论：首次 P0/P1 归零

| 复审轮 | 版本 | 发现 P0 | 发现 P1 | 综合分 |
|-------|------|--------|--------|------|
| 第二~五轮 | v0.2.2~v0.2.7 | 3~4 / 轮 | 3~5 / 轮 | 68~72 |
| 第六轮 | v0.2.8-review | 4（CWD 根因 bug） | 4 | 65（历史最低） |
| **第七轮** | **v0.2.9-review** | **0** | **0** | **82**（历史最高） |

本轮首次 P0/P1 归零 —— 继续设计层 review 的边际价值极低。

#### 本轮小发现（全部 P2/P3，不修也不影响使用）
- **P2-V09-1**：`grep "default"` 仍有 10 处散落（FIX-066 只改了 1 处 Option 默认值），行为等价，仅"集中管理"目标未达成
- **P3-V09-1**：mdc 安装脚本 bash 反斜杠转义可读性差（实测能跑，只是看起来"脏"）
- **P3-V09-2**：fallback 扫描目录硬编码 `['cursor','projects','dev','repos']`
- **META-V09-1**：mdc 的"先 Phase 4 再 Phase 1"契约**同一会话内无法立即生效**（Cursor 规则启动时加载一次，不是 bug，是平台机制）

#### 战略判断：进入"纯使用模式"

当前 `memory/capability-index.yaml` 累计：
- `default`: 0 · `refactoring`: 2 · `architecture_review`: 1 · `cwd_integration_test`: 1

**总计 4 次真实执行**。Forger `count ≥ 5` 阈值**一次都未触发**。整套涌现式设计**尚未被真实数据验证**。

继续"设计→复审→修"循环的边际价值越来越小。真正的风险是——**没人知道这个系统在真实积累 100 次任务后会长什么样**。

#### 触发下次 review 的条件（任一满足）
1. 累计 20+ 次真实 task（目前 4 次，距阈值 16 次）
2. Forger 首次真实触发（某 task_type 达 count ≥ 5）
3. 2 周时间到（约 2026-05-01）
4. 遇到明显的使用层 bug / 体验问题

---

## 架构决策记录 (ADR)

### ADR-001: Phase 1 预判采用 CoT Prompt 而非 Hidden State 分类
**日期**: 2026-04-15 · **状态**: 已决定

**背景**：CapBound 论文证明 LLM hidden states 在"能/不能"任务上 98%+ 可分。但 API 模型（GPT-4o / Claude）不暴露 hidden states。
**决策**：先用 CoT Prompt 实现（通用），把 Hidden State 路径列为 Stage 5 研究课题。
**后果**：Phase 1 token 成本约 500/次。

### ADR-002: Skill Registry 采用 YAML 持久化而非数据库
**日期**: 2026-04-15 · **状态**: 已决定

**理由**：轻量开源项目，YAML 对人类友好且 Git 可读。
**后果**：单文件管理，容量上限约 10000 条 skill（> 1 MB 性能下降）。

### ADR-003: capability_gains 静态手动填写 + 动态校准
**日期**: 2026-04-15 · **状态**: 已决定

**决策**：初始由开发者根据经验填写（Registry 种子），Phase 4 通过 EMA 动态校准。
**v0.2.6 补充**：涌现式转向后，种子不再预填，Forger 生成的草稿初始 `capability_gains` 默认 10（见 FIX-057）。

### ADR-004: 自创建 Skill 必须经过用户审核才能入库
**日期**: 2026-04-15 · **状态**: 已决定

**决策**：Forger 生成草稿到 `memory/self-made/`，用户审核后显式 `sf push` 入库，不自动合并。
**理由**：防止 AI 幻觉污染 Registry。

### ADR-005: Gap 分级从 3 档扩展到 5 态（借鉴 KnowSelf）
**日期**: 2026-04-15 · **状态**: 已决定

| Gap | 状态 |
|-----|------|
| < 5 | `independent` |
| 5~15 | `light-hint` |
| 15~30 | `suggest` |
| 30~50 | `force-enhance` |
| ≥50 | `out-of-scope` |

### ADR-006: 启动方式 — Cursor 规则 + Python 引擎双路并存
**日期**: 2026-04-15 · **状态**: v0.2.0 确认 mdc 为权威

**决策**：Cursor 对话场景以 `.cursor/rules/skillforge.mdc` 为权威；Python 批量场景用 `sf run` / `sf analyze`；两者共享 `capability-index.yaml`。

### ADR-007: 记忆索引三层设计
**日期**: 2026-04-15 · **状态**: 已决定

| 层 | 文件 | Token | 作用 |
|----|------|-------|------|
| L0 | `capability-index.yaml` | < 500 | Phase 1 预判校准 |
| L1 | `trajectories/{type}/` | < 1K | 按类型加载执行轨迹（仅 Python 批量） |
| L2 | `reflections.md` | < 2K | 失败教训注入 Phase 1 |

### ADR-008: 虚拟 Skill 机制（解耦 Registry 与物理文件）
**日期**: 2026-04-17 · **状态**: v0.1.1 引入，v0.2.5 扩展为 `sf show` 的 fallback

**决策**：Registry 条目不强制要求物理 SKILL.md。`executor.py::_synthesize_minimal_skill_card` 和 `cli.py::_build_inline_skill_context` 可合成 100~150 tokens 的最小 skill 卡片。

### ADR-009: Cursor ↔ Python 闭环的桥接策略
**日期**: 2026-04-17 · **状态**: v0.2.3 替换为 `sf update-l0` 单一入口

**演化**：
- v0.1.1 双路桥接（`sf eval` / `sf ingest` via `cursor-timings.md`）
- v0.2.2 废弃 `cursor-timings.md`（打扰用户）
- v0.2.3 统一为 `sf update-l0` 作为唯一写入入口

---

## 已知技术债务

| ID | 严重性 | 描述 | 延后原因 |
|----|------|------|--------|
| TD-P2-V09-1 | Low | `grep "default"` 仍有 10 处散落（`cli.py` / `engine.py` / `evaluator.py` / `reflexion.py`），FIX-066 只改了 1 处 | 行为等价，不影响功能；下次触碰文件时顺手改 |
| TD-P3-V09-1 | Low | mdc 安装脚本 bash 转义 `\"\$_SF_ROOT\"` 可读性差 | 实测能跑，仅视觉问题 |
| TD-P3-V09-2 | Low | mdc 安装 fallback 目录硬编码 `['cursor','projects','dev','repos']` | 99% 场景走 `importlib` 优先路径，fallback 仅边缘场景 |
| TD-P3-V09-3 | Low | `_find_self_made_drafts` 线性扫描 | 目录内 < 50 个文件前无感知延迟 |
| TD-META-V09 | Info | mdc 行为契约在**同一会话内无法立即生效**（Cursor 启动时加载规则） | 平台机制，非 bug。修改 mdc 后需重启会话验证 |

---

## 反思记录

反思内容由 `sf update-l0 --rating 1` 自动追加模板骨架到 `memory/reflections.md`，在本文档中**不再重复展开**。

**当前反思位置**：`memory/reflections.md`（append-only）

**反思写入约束**（由 mdc Phase 4 · 第三步强制）：
- ❌ 严禁外部归因：`"用户任务描述不清"` / `"模型能力不足"` / `"文档缺失"` / `"时间不够"`
- ✅ 必须从三个内因维度找根因：
  1. 对任务理解是否准确？
  2. 对复杂度预判是否到位？
  3. 执行策略是否合适？

---

## 学术对照表

| 论文 | 核心思想 | SkillForge 对应模块 |
|------|---------|------------------|
| **[KnowSelf](https://arxiv.org/abs/2502.04563)** (ACL 2025) | Agent 漫灌执行，不先判断缺什么 | 五态 Gap 分级设计 |
| **[CapBound](https://arxiv.org/abs/2504.02419)** (清华 & 蚂蚁) | Hidden states 中"能/不能"98%+ 线性可分 | Phase 1 能力预判（Stage 5 白盒路径） |
| **[Reflexion](https://arxiv.org/abs/2303.11366)** (NeurIPS 2023) | 自然语言反思替代梯度更新 | L2 反思日志 + Stage 4 ReflectionLoader |
| **[MAR / Multi-Agent Reflexion](https://arxiv.org/abs/2402.07927)** | 多角色辩论解决确认偏误 | Stage 3 MARCoordinator（Optimist/Skeptic/DomainExpert + Judge） |
| **[Hermes Agent](https://arxiv.org/abs/2407.00418)** | 失败后自动生成可复用 SKILL.md | SkillForge-Forger 模块（v0.2.6 涌现式生长） |
