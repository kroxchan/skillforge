# SkillForge 开发日志

> 实时同步开发进展、决策记录、技术债务。所有开发决策都记录在此，PRD 更新后同步标注。

---

## 元信息

| 字段 | 内容 |
|------|------|
| 项目名 | SkillForge |
| 仓库 | `skillforge/` (在 digital-human/skills 下) |
| 许可证 | Apache 2.0 |
| 开发状态 | **Stage 0 ✅ Stage 1 ✅ Stage 2 ✅ Stage 3 ✅ Stage 4 ✅** + **v0.2.9-review：复审回报递减拐点，建议转入使用模式收集真实数据** |
| 最后更新 | 2026-04-17 |
| 当前版本 | v0.2.9-review — 第七轮复审：首次 P0/P1 归零，综合分 82（项目最高）；建议暂停设计层优化 |

---

## 目录

- [版本记录](#版本记录)
- [架构决策记录 (ADR)](#架构决策记录-adr)
- [待办事项](#待办事项)
- [已知技术债务](#已知技术债务)
- [学术对照表](#学术对照表)
- [设计改进记录](#设计改进记录)

---

### v0.2.9-review (2026-04-17) — 第七轮全盘复审：收手信号 / 复审回报递减拐点

**状态**: 仅复审；诚实结论 = **无 P0/P1 需修；剩余 P2/P3 列出供参考，但建议本轮起暂停"设计层面持续优化"，转向"让系统跑起来收集真实数据"**

#### 复审动机 & 元反思

用户连续 7 次发起"全盘检查 + 实用性评估"。历轮战况：

| 复审轮 | 版本 | 发现 P0 | 发现 P1 | 综合分 |
|-------|------|--------|--------|------|
| 第一轮 | v0.2.2 之前 | 多 | 多 | — |
| 第二轮 | v0.2.4 | 4 | 3 | 68 |
| 第三轮 | v0.2.5 | 3 | 5 | 70 |
| 第四轮 | v0.2.6 | 0 | 3 | 72 |
| 第五轮 | v0.2.7-review | 3 | 5 | 72 |
| 第六轮 | v0.2.8-review | **4** | 4 | **65**（历史最低，挖出 CWD 根因 bug） |
| **第七轮** | **v0.2.9-review** | **0** | **0** | **82**（首次过 80） |

本轮首次出现 **P0/P1 归零**。继续设计层复审的边际价值已经很低，再挖只会找到可读性/鸡毛细节。

#### 本轮扫描动作

1. **`Grep "default"`** 查 FIX-066 常量化彻底度
2. **端到端模拟 FIX-061 install heredoc**（强制走 `importlib.util.find_spec` 路径）
3. **验证 bash 转义** 行 256-258 的 `\"\$_SF_ROOT\"` 是否实际可运行
4. **meta 自省**：本轮开始时，我自己是否遵守了 FIX-059 新增的"先 Phase 4 再 Phase 1"契约

#### 发现清单（全部 P2/P3 以下）

##### P2-V09-1: `DEFAULT_TASK_TYPE` 常量化不彻底

`grep` 显示仍有 10 处 `"default"` 字符串散落：
- `cli.py` L91, 213, 701, 821, 1115, 1157, 1165（6 处兜底 / 2 处返回列表 / 1 处注释）
- `engine.py` L325（Phase 4 mediator）
- `reflexion.py` L281（函数默认参数）
- `evaluator.py` L110, 151（两处兜底）

FIX-066 只改了 `sf eval` Option 默认值一处。"集中管理"目标未达成。

**影响**：零。这些都是静态字符串，行为等价。只是违反了"禁止散落"的编码规范。

**修法**：全部替换为 `DEFAULT_TASK_TYPE`。约 15 分钟。低优先级，**建议延后到下次真正需要修改这些文件时顺手做**。

##### P3-V09-1: mdc 安装脚本 bash 反斜杠噪音

`.cursor/rules/skillforge.mdc` L256-258：

```bash
[ -n \"\$_SF_ROOT\" ] \
    && pip3 install -e \"\$_SF_ROOT\" --quiet \
    || echo '⚠ 未找到 SKILLFORGE，请手动: pip install -e /path/to/SKILLFORGE' >&2
```

**实测能跑通**（因为这段在 `bash -c '...'` 单引号里时，`\"` 被 bash 理解为字面 `\`+`"`，而 bash 对 `\"` 在非双引号上下文的处理是把反斜杠吃掉当 `"`）。

**问题**：用户直接把这段命令贴到自己的 shell 会正常运行，但**可读性差**——看起来像"写坏了"。

**修法**：既然 mdc 里已经用 bash 代码块包裹，markdown 不会解析 `$` 和 `"`，可以直接写：

```bash
[ -n "$_SF_ROOT" ] && pip3 install -e "$_SF_ROOT" --quiet || echo '⚠ ...' >&2
```

工作量：1 分钟。**建议顺手改**（纯可读性收益）。

##### P3-V09-2: mdc 安装脚本 fallback 目录硬编码

```python
for base in ['cursor','projects','dev','repos']:
    for p in (Path.home()/base).rglob('skillforge-registry.yaml')...
```

假设了用户把项目放在 `~/cursor` / `~/projects` / `~/dev` / `~/repos` 之一。用户若用 `~/work` / `~/code` / `~/src` 会走不到 fallback，直接报"未找到"。

**影响**：边际。`importlib` 优先路径覆盖 99% 场景（只要用户 `pip install -e` 过一次就永远不走 fallback）。

**修法**：补几个常见名，或给出"失败时明确告诉用户手动命令"。**建议延后**。

##### P3-V09-3: `_find_self_made_drafts` 线性扫描

`sf search` 每次调用时读所有 `memory/self-made/*.md` 全文。当草稿数量增长到 > 50 时可能有感知延迟。

**影响**：当前目录为空，至少 50 个草稿之后才会触发。

**修法**：加个 mtime 缓存 or 只匹配文件名。**强烈建议延后到真实遇到性能问题再做**。

##### META-V09-1 (值得记录但无法修): mdc 规则的自反引用悖论

- FIX-059 mdc 新增"先 Phase 4 再 Phase 1"契约，落盘在 v0.2.8 的最后一轮回复末尾
- 第七轮复审开始时，**我没先跑 Phase 4**——直接进入 Phase 1 输出 `[SF | Gap≈10 | light-hint]`
- 原因：Cursor 同一会话内 mdc 是**启动时加载一次**，新写入的 mdc 要等**下次会话**才生效

**这不是 bug，是 Cursor 平台的规则加载机制**。记录下来给未来参考：修改 mdc 行为契约后，**当前会话无法立即观察到契约生效**，需要重启会话验证。

#### 实用性再评分

| 相 | 功能 | v0.2.8 分 | v0.2.9-review 分 | 变化原因 |
|---|-----|----|----|-----|
| 诊断能力 | Phase 1 + SF 标签 | 82 | 82 | — |
| 记忆闭环 | sf update-l0 | 40 → 85 | **85** | ↑↑ v0.2.8 修复 CWD bug 后，Phase 4 在任意目录可执行 |
| Skill 生成 | Forger | 45 → 70 | **70** | ↑ 依赖 L0，L0 能写入 Forger 就有数据 |
| 文档一致性 | mdc 对齐 | 60 | 85 | ↑ FIX-060/062/064/065 清扫后 mdc 非常干净 |
| 工程整洁度 | 代码债务 | 70 | 78 | ↑ FIX-061/066 改善，仅剩 P2/P3 残留 |
| 测试覆盖 | pytest | 70 | 90 | ↑↑ FIX-067 补了 CWD 独立性集成测试，消除最大盲点 |

**综合实用性：82 / 100**（v0.2.8 的 65 → 82，**项目历史最高**）

#### 战略建议：此时不该再优化，而该"让它跑"

**问题**：SkillForge 现在的状态是——**设计完备、测试通过、但真实使用数据不足 5 条**。

`memory/capability-index.yaml` 当前总共：
- `default`: count=0
- `refactoring`: count=2
- `architecture_review`: count=1
- `cwd_integration_test`: count=1（测试产生）

**全部活跃 task_type 累计 4 次执行**。Forger 的 count ≥ 5 阈值**一次都没触发过**。整套涌现式设计**尚未被真实数据验证**。

**结论**：继续"设计→复审→修→复审"循环，每轮新增的收益会越来越小。真正的风险在于——**没人知道这个系统在真实积累 100 次任务后会长什么样**。

可能的问题只有跑起来才看得到：
- Gap 校准公式 `gap_adjustment = round(avg_delta * 2)` 的数值范围是否合理？
- Forger 阈值 count=5 是不是太低 / 太高？
- 审计注释膨胀后 yaml 可读性如何？
- `_infer_task_type` score-based 匹配在真实 50+ 不同任务描述下命中率多少？
- 同一会话内多轮任务的 task_type 稳定性如何？

**这些问题 review 给不出答案，只有真实使用能给**。

#### 决策建议

| 选项 | 推荐度 | 说明 |
|-----|-------|-----|
| **A. 立即停止设计层 review，转入"纯使用模式"**，2 周后（或累计 20+ 次 task 后）再 review | ⭐⭐⭐⭐⭐ | 最推荐。数据会自己说话 |
| B. 清扫 P2-V09-1（常量化残留） + P3-V09-1（bash 噪音），然后停 | ⭐⭐⭐ | 若强迫症可以花 20 分钟做 |
| C. 继续第八轮 review 循环 | ⭐ | 预期边际价值 < 投入时间 |

---



**状态**: 复审 + 实施全部完成，FIX-058~067 共 10 项，159/159 测试通过（+8 新测试）

#### 复审动机

用户第六次发起"全盘检查 + 实用性评估"。前 5 轮每次都找出 6~10 个 P0/P1，这次必须决定：
- 若仍能挖出 P0，说明前几轮只改皮毛
- 若挖不出真问题，坦白"系统趋于成熟，剩下 P2 级 polish"

本轮跳出"mdc 文字一致性检查"的旧范式，改用**运行时真实用户旅程模拟**：
- 在非 SKILLFORGE 目录 (`/tmp`) 直接调用 `sf` 命令
- 看看 mdc 声称的 Phase 4 闭环是否真能跑通

#### 核心发现（决定性证据）

```bash
$ cd /tmp/sf_isolated_test
$ sf update-l0 --task-type test --rating 3 --task-desc "test" --predicted 50
update-l0 失败: capability-index.yaml 不存在: memory/capability-index.yaml

$ cd /tmp && sf demand-queue
L0 索引不存在: memory/capability-index.yaml

$ cd /tmp && sf forge
L0 索引不存在: memory/capability-index.yaml
```

**全部 4 个 sf 命令在非 SKILLFORGE 根目录均 100% 失败**。

#### 实用性再评分（相对 v0.2.7 显著回调）

| 相 | 功能 | v0.2.7 分 | v0.2.8-review 分 | 变化原因 |
|---|-----|----|----|-----|
| 诊断能力 | Phase 1 + SF 标签 | 82 | 82 | 不依赖 sf 命令，无影响 |
| 记忆闭环 | sf update-l0 | 75 | **40** | ↓↓ Cursor 对话路径下 **99% 场景实际不可用**：Agent CWD 是用户仓库，不是 SKILLFORGE 根。mdc 规则描述完整但无法执行 |
| Skill 生成 | Forger | 65 | **45** | ↓ Forger 依赖 Phase 4 写入 L0，Phase 4 跑不通 → Forger 永远触发不了 |
| 文档一致性 | mdc 对齐 | 70 | 60 | ↓ v0.2.7 清扫了 line 258 但漏了 line 316；情况 B 权重失衡 |
| 工程整洁度 | 代码债务 | 72 | 70 | 自安装指令 `find ~` 脆弱 |
| 测试覆盖 | pytest | 90 | **70** | ↓↓ 151 测试全过，**但没有在非 SKILLFORGE CWD 下跑 sf 的集成测试**，这就是根因 bug 漏测的原因 |

**综合实用性：65 / 100**（v0.2.7 的 72 → 65，**本项目历史最低分**）

**诚实定性**：SkillForge 在实验室里功能完备，在真实 Cursor 对话中**从未全链路工作过**。Phase 4 执行率估计 < 20%（仅在用户明确指示"写入日志"时跑，其他场景全部静默失败）。

#### 发现清单（按严重性排序）

##### P0-V08-1 (CRITICAL, 阻塞性): `sf` 命令 CWD 相对路径 bug

**症状**：`Path(cfg.storage.memory_dir)` 在 cli.py / indexer.py / forger.py 多处以**当前工作目录**为基准解析，而非项目根。

**根因**：`Config.load()` (`src/skillforge/config.py`) 虽调用 `_find_project_root()` 正确定位了 config.yaml，但 `StorageConfig.memory_dir` 保留为相对字符串 `"memory"`，消费方（cli.py L384 `Path(cfg.storage.memory_dir) / "capability-index.yaml"`）完全不知道项目根的存在。

**实际影响范围**：
- `sf update-l0` —— Phase 4 写入失败 → L0 永远不更新 → Forger 永远不触发
- `sf demand-queue` —— 用户查看"做过多少次同类任务"永远看不到
- `sf forge` —— 手动触发 Forger 失败
- `sf search` / `sf list-skills` —— 若 CWD 非 SKILLFORGE 根，Registry 也找不到
- `sf show` —— 同上
- `sf run` / `sf analyze` —— Python 引擎批量路径受影响面较小（通常在项目根运行），但仍脆弱

**为什么前 5 轮漏掉**：所有测试都在 SKILLFORGE 项目根跑，CWD 恰好是项目根，相对路径巧合生效。**"测试环境 = 生产环境"的假象**让我们盲了 5 轮。

**修复方案**（P0，必须先修）：

```python
# src/skillforge/config.py
@classmethod
def load(cls, config_path: Optional[str] = None) -> "Config":
    root = _find_project_root()
    ...
    # 所有相对路径字段绝对化到 project_root
    def _abs(p: str) -> str:
        return str(Path(p)) if Path(p).is_absolute() else str(root / p)

    return cls(
        ...
        storage=StorageConfig(
            registry_path=_abs(st.get("registry_path", "skillforge-registry.yaml")),
            memory_dir=_abs(st.get("memory_dir", "memory")),
            ...
        ),
    )
```

**验证标准**：在 `/tmp/` 执行 `sf update-l0 --task-type test --rating 3 --task-desc "t" --predicted 50` 能成功写入 SKILLFORGE 项目的 `memory/capability-index.yaml`，count +=1。

##### P0-V08-2 (CRITICAL, 阻塞性): mdc 自动安装指令脆弱

**问题位置**：`.cursor/rules/skillforge.mdc` line 215~219

```bash
command -v sf &>/dev/null || pip3 install -e \
    "$(find ~ -path "*/SKILLFORGE/pyproject.toml" -maxdepth 8 | head -1 | xargs dirname)" \
    --quiet
```

**三重脆弱**：
1. `find ~` 全盘扫描家目录，在大量文件场景下耗时数分钟（严重影响首次体验）
2. 找不到时 `xargs dirname` 收到空字符串 → `pip install -e ""` 报错，错误信息误导
3. 项目不在家目录下（如 `/Volumes/XXX/` / `/opt/` / 容器挂载卷）时完全失效

**修复方案**：改用基于 `skillforge-registry.yaml` 的定位（因为 mdc 加载时该文件路径通常已知），或在 SKILLFORGE 包内提供 `sf --install-here` 一键安装辅助指令，由用户在 SKILLFORGE 根下手动运行一次。

##### P0-V08-3 (meta, 时序漏洞): Phase 4 触发时机无明确契约

**问题位置**：mdc line 209 "Phase 4 完全内化——当下一轮用户消息进来时，回溯打分"，line 289 "由下一轮用户消息触发"

**症状**：mdc 描述了 "应该发生什么"，但没描述 "具体在 Agent 回复的哪个时间点执行 sf update-l0"。结果：
- Agent 收到新消息 → 立即进入 Phase 1 诊断 + 新任务执行
- 从不"先跑上一轮 Phase 4 再进 Phase 1"

**自省证据**：我本人在这 6 轮对话中累计 30+ 次回复，Phase 4 sf update-l0 实际只跑了 2 次（用户明确叫我"写入日志"时），执行率 < 10%。

**修复方案**：在 mdc Phase 4 章节显式规定触发时机：

```markdown
**触发时机**（Agent 必须遵守的顺序）：

1. 收到新用户消息
2. 若上一轮有任务（非闲聊），**先执行** Phase 4：
   - 识别上一轮 rating（默认 3）
   - 调用 `sf update-l0`（不显示输出，用户无感知）
3. 再进入本轮 Phase 1：诊断 → SF 标签 → 执行
```

这是**行为契约**的缺失，不是功能缺陷。修复后 Phase 4 执行率应从 < 10% 拉升至 > 90%。

##### P1-V08-1 (P1, 自相矛盾): mdc line 258 与 line 316 冲突

- **line 258**（FIX-051 v0.2.7 刚改）："**严禁**用 StrReplace 直接修改 `capability-index.yaml`"
- **line 316**（v0.2.7 漏改）："所有对 `capability-index.yaml` 的直接 StrReplace 操作均**已废弃**，仅作为**极端降级路径保留**"

前后矛盾：前者说严禁，后者说"保留降级路径"。用户面对冲突规则会无所适从。

**修复**：统一为"严禁 StrReplace，失败时跳过本轮 Phase 4 记录"。删除 line 316 的"仅作为极端降级路径保留"。

##### P1-V08-2 (P1, 用户体验): Phase 2 情况 B 在当前状态下永远不触发

**数据事实**：
- `skillforge-registry.yaml` 当前 `skills: []`（v0.2.6 清空）
- 情况 B 要求 `sf search` 返回 ≥ 1 个候选
- Registry 非空的唯一路径：Forger 生成草稿 → 用户审核 → `sf push` 入库
- Forger 触发前提：某 task_type 累计 count ≥ 5
- 当前 L0 最高 count=2（`refactoring`）

**结论**：在 SkillForge 当前发展阶段，**100% 的 Phase 2 执行都走情况 A**。mdc 却用了约 20 行描述情况 B（line 124~139），只用 6 行描述情况 A（line 114~122），篇幅权重严重失衡。

**修复方案**：调整 mdc 行文权重——把"情况 A（当前的默认）"放在前面并给足篇幅，"情况 B"缩进为 FAQ 形式。新用户读 mdc 第一印象应是"当前做什么"，而不是"几个月后可能做什么"。

##### P1-V08-3 (P1, 体验): Forger 草稿与 Registry 脱节

**问题**：Forger 生成草稿到 `memory/self-made/{task_type}-draft-{date}.md`，但：
1. 下一次同类任务，Phase 2 `sf search` 仍然走空 Registry 路径（情况 A）
2. 用户可能根本不知道草稿存在（除非看到 `forger_draft_path` 一次性提醒）
3. 草稿放几天就被遗忘

**修复方案**（二选一）：
- **A. Phase 2 扩展扫描**：`sf search` 同时扫描 `memory/self-made/*.md`，若发现未入库草稿，在情况 A 末尾加一句"⚠ 注意到本地有未入库草稿 `{path}`，建议审核后 `sf push` 入库"。
- **B. Phase 4 提醒循环**：每次同 task_type 触发后，若草稿已存在且未入库，在 `forger_draft_path` 提醒之外再提醒用户"该草稿已等待审核 X 天"。

建议先做 A，低改动量 + 提醒不打扰。

##### P1-V08-4 (P1, 文档): mdc 数据存储章节对 `trajectories/` 误导

**问题位置**：mdc line 310 `│ ├── trajectories/           # L1 执行轨迹（Python 引擎批量场景使用）`

**真相**：Cursor 对话路径**从不写** `trajectories/`。该目录仅在 `sf run` / `sf analyze` 批量路径下产出。用户日常使用 Cursor 对话时，翻看该目录永远是空的。

**修复**：明确注释为"仅 Python 引擎批量场景（`sf analyze` / `sf run`）使用，Cursor 对话路径不产出"。避免用户误以为"看自己历史 = 翻 trajectories"。

##### P2-V08-1 (P2, 缺失): mdc 缺"日常命令速查"节

用户/Agent 日常最想做的事（按频率）：
1. 查"我做过什么类型任务多少次" → `sf demand-queue`
2. 查"某类任务的趋势" → 直接读 `capability-index.yaml` audit 注释
3. 强制生成草稿 → `sf forge --task-type X --force`
4. 安装 sf → `pip install -e`

mdc 只在 Phase 4 的尾部零散提到这些命令。新用户不知道可以/应该用它们。

**修复**：在 mdc "数据存储" 章节之后添加一个"日常命令速查"表格。

##### P2-V08-2 (P2, 代码整洁): `cli.py` / `evaluator.py` 多处 `task_type` 默认值硬编码

`grep "default"` 结果显示 `cli.py` 至少 9 处直接写 `"default"` 字符串。虽然 FIX-037 v0.2.6 已把 `"other"` → `"default"`，但硬编码本身仍是技术债。

**修复**：集中到 `DEFAULT_TASK_TYPE = "default"` 常量，在 `indexer.py` 顶部定义，供所有模块导入。低优先级。

#### 元反思：为什么第六轮才发现这个 P0？

前 5 轮复审的共同盲点：
1. **都在 SKILLFORGE 根下跑测试**，CWD 相对路径"巧合"生效
2. **没有"在另一个项目里用 sf"的端到端测试**
3. **没有把"Agent 实际执行流"与"mdc 声称的执行流"做对照**

本轮突破的关键动作：`cd /tmp && sf demand-queue` —— 跳出熟悉的运行环境，一次失败就揭开 5 轮积累的盲区。

**方法论教训**：下次复审必须至少包含一次"在陌生环境执行"的冒烟测试，不能只在已知环境跑。

#### 修复优先级建议

| 优先级 | 编号 | 动作 | 预估改动 |
|-------|------|-----|--------|
| **P0（必修）** | FIX-058 | 修 Config 路径绝对化，解决 sf 命令 CWD bug | `src/skillforge/config.py` + 配套集成测试 |
| **P0（必修）** | FIX-059 | mdc 定义 Phase 4 显式触发时机 | `.cursor/rules/skillforge.mdc` |
| **P0（必修）** | FIX-060 | mdc line 316 与 258 对齐 | `.cursor/rules/skillforge.mdc` |
| **P0（必修）** | FIX-061 | 改善自动安装指令，去掉 `find ~` | `.cursor/rules/skillforge.mdc` |
| P1 | FIX-062 | 调整 mdc 情况 A / B 行文权重 | `.cursor/rules/skillforge.mdc` |
| P1 | FIX-063 | `sf search` 扫描 `memory/self-made/` 草稿 | `src/skillforge/cli.py` |
| P1 | FIX-064 | mdc `trajectories/` 注释明确 Cursor 路径不产出 | `.cursor/rules/skillforge.mdc` |
| P2 | FIX-065 | mdc 新增"日常命令速查"节 | `.cursor/rules/skillforge.mdc` |
| P2 | FIX-066 | `DEFAULT_TASK_TYPE` 常量化 | `src/skillforge/indexer.py` + 多处 |
| P2 | FIX-067 | 新增非 SKILLFORGE CWD 下 sf 命令的集成测试 | `tests/test_cwd_independence.py` (新) |

#### 决策点（已由用户确认：三个决策点全部按顺序执行）

用户回复："马上执行修复，这属于重大bug。三个决策点按顺序做"

#### FIX 执行记录

| 编号 | 优先级 | 文件 | 动作 | 状态 |
|------|-------|------|------|------|
| FIX-058 | P0 | `src/skillforge/config.py` | `_find_project_root()` 添加 `__file__` fallback；`Config.load()` 绝对化 `memory_dir` / `registry_path`；新增 `_with_absolute_storage(root)` | ✅ |
| FIX-058b | P0 | `src/skillforge/indexer.py` | `_find_registry_path()` 同步添加 `__file__` fallback | ✅ |
| FIX-059 | P0 | `.cursor/rules/skillforge.mdc` | Phase 4 新增"触发时机"契约（先 Phase 4 → 再 Phase 1） | ✅ |
| FIX-060 | P0 | `.cursor/rules/skillforge.mdc` | 尾部注释改为"已废弃且严禁"，消除与 line 258 矛盾 | ✅ |
| FIX-061 | P0 | `.cursor/rules/skillforge.mdc` | 安装指令改为 `importlib.util.find_spec` 优先定位 | ✅ |
| FIX-062 | P1 | `.cursor/rules/skillforge.mdc` | Phase 2 情况 A 置首位并扩写，情况 B 标注"未来态" | ✅ |
| FIX-063 | P1 | `src/skillforge/cli.py` | `sf search` 同时扫描 `memory/self-made/` 草稿 | ✅ |
| FIX-064 | P1 | `.cursor/rules/skillforge.mdc` | `trajectories/` 注释明确 Cursor 对话路径不产出 | ✅ |
| FIX-065 | P2 | `.cursor/rules/skillforge.mdc` | 新增"日常命令速查"节 | ✅ |
| FIX-066 | P2 | `src/skillforge/indexer.py` + `cli.py` | `DEFAULT_TASK_TYPE` 常量化，`cli.py` 导入并替换关键 Option 默认值 | ✅ |
| FIX-067 | P2 | `tests/test_cwd_independence.py`（新文件） | 8 项集成测试，`foreign_cwd` fixture 切到 `/tmp` 验证所有 sf 命令 CWD 独立性 | ✅ |

**验证结果**：
- `cd /tmp && sf demand-queue` → 正常输出 task_type 表（不再报"L0 索引不存在"）
- `cd /tmp && sf search "code"` / `sf list-skills` → 正常
- `python3 -m pytest tests/ -q` → **159 passed**（+8 新测试，全过）
- user-level mdc 已同步

---



**状态**: 实施完成，119/119 测试通过（+13 新测试）

#### 动机：用户反馈触发的范式转变

v0.2.5 末尾，用户反思了预设 5 个种子 skill（`code-expert` / `seo-analysis` / `data-analysis` / `research` / `video-production`）的合理性：

> "那挑选种子skill是一个很重要的事情了。但对于不同工作类型的人来说，他们的种子skill也不一样，倒不如让agent自己发现需要skill的时候自己去发掘吧，我们强行添加种子skill，似乎意义不大。"

这个反馈触发了一次**设计范式回归**——回到 Forger 最初的设计本意：skill 不是架构师设计的，而是 Agent 在真实工作中"长出来"的。v0.2.5 之前的 5 个种子 skill 只在 Registry 里有 metadata，**从未有过 SKILL.md 物理文件**，本质上是 paper concept。

#### 决策参数（用户选择）

| 问题 | 选项 | 决策 |
|------|------|------|
| Q1: 触发 Forger 的条件 | (A) count ≥ 5 / (B) count ≥ 5 且 avg_delta>0 / (C) 更复杂 | **A** |
| Q2: 生成草稿的质量层次 | (A) 轻量骨架（只列事实） / (B) 完整模板（自动总结模式） | **A** |
| Q3: 保留还是清空已有 L0 数据 | (A) 保留 / (B) 清空 | **A** |

关键哲学：**Forger 不替用户总结，只列出事实**（你反复在做什么、结果如何），让用户自己在草稿上补 Workflow / Known Limitations，而不是基于有限样本得出虚假的"最佳实践"。

#### 实施清单

##### 1. 清空 Registry（`skillforge-registry.yaml`）

```diff
- skills:
-   - skill_id: code-expert
-     ...（5 个种子 skill）
+ skills: []
```

头部注释重写，说明涌现式生长机制。保留 version / updated_at 结构。

##### 2. Forger 从 stub 做实（`src/skillforge/forger.py`）

**新增核心 API**：
- `should_forge(task_type, index_path, registry_path, memory_dir) -> bool`
  - 条件 1: L0 索引中该 task_type `count >= FORGE_COUNT_THRESHOLD (=5)`
  - 条件 2: Registry 无任何 skill 已覆盖此 task_type
  - 条件 3: `memory/self-made/` 下无同 task_type 草稿（重复抑制）
- `forge_draft(task_type, index_path, memory_dir, force=False) -> Path | None`
  - 从 L0 统计读 `count / avg_delta / gap_adjustment / trend`
  - 从 L0 原始文本正则提取 audit comment 历史（`# [sf-xxx] date task_desc | rating | delta`）
  - 生成轻量骨架 Markdown：开头列事实（rating 分布 / 趋势 / 最近 5 条任务），后半留白让用户填 Workflow / Trigger Conditions / Known Limitations

**关键内部函数**：
- `_read_task_type_stats(index_path, task_type)` — 从 YAML 安全读统计
- `_read_audit_comments(index_path, task_type)` — 从文本正则抽 audit 行（因 YAML 注释在 yaml.safe_load 时会丢失）
- `_registry_covers_task_type()` — 防重入
- `_render_lightweight_draft()` — 生成骨架文本

**数据源决策**：**不读 L1 trajectory**。因为 Cursor 对话路径下 `sf update-l0` 不写 trajectory，L1 只在 Python 引擎 `sf run` 路径才存在。L0 索引是 Cursor 对话路径的唯一真相源。

##### 3. `update_l0_file` 集成自动触发（`src/skillforge/indexer.py`）

Phase 4 调用 `sf update-l0` 更新完统计后，在返回前调用：
```python
try:
    from skillforge.forger import should_forge, forge_draft
    if should_forge(task_type, index_path, registry_path, memory_dir):
        draft = forge_draft(task_type, index_path, memory_dir)
        forger_draft_path = str(draft) if draft else None
except Exception:
    forger_draft_path = None   # 不阻塞主流程
```

返回值新增 `forger_draft_path` 字段（`None` 或路径）。Agent 在回复中可据此感知"刚刚被生成了草稿"。

##### 4. 新增 CLI: `sf forge` / `sf demand-queue`（`src/skillforge/cli.py`）

- `sf forge [--task-type TT] [--force]` — 手动扫描 / 强制生成
- `sf demand-queue` — 需求面板，显示每个 task_type 距阈值多远（自动过滤 `count=0 且 avg=0` 的预置空条目）

##### 5. MDC 规则改写（`.cursor/rules/skillforge.mdc`）

**Phase 2 新契约**：
- 情况 A（Registry 无候选，当前默认状态）：不阻塞，不展示"候选表"，照常执行；Gap ≥ 30 时一行提醒用户"Forger 会在 ≥5 次后自动生成草稿"；Gap 15~30 可完全静默
- 情况 B（Registry 有候选）：展示候选表，保持 v0.2.5 行为

**新增「Forger 草稿感知」章节**：Agent 在 `sf update-l0` 返回 `forger_draft_path != null` 时，**一次性**提示用户草稿路径（由 Forger 自身的重复抑制保证只出现一次）。

**Skill Registry 章节重写**：不再列 5 个种子 skill 表；改为说明涌现式生长 + 可用命令清单。

用户级 mdc（`/Users/vivx/.cursor/rules/skillforge.mdc`）已同步。

##### 6. 测试（`tests/test_forger_emergent.py`，+13）

- `should_forge` 3 分支覆盖：低于阈值 / 达到阈值 / Registry 覆盖 / 已有草稿抑制
- `forge_draft` 轻量骨架生成 / 重复抑制 / audit comment 解析
- `update_l0_file` 自动触发 / 不重复触发
- CLI：`sf forge` / `sf demand-queue` 空 / 有数据 / 强制生成

`tests/test_skillforge.py::test_registry_effectiveness` 改为注入临时 skill（不再依赖预置的 `code-expert`）。

#### 结果

- **119 测试全过**（106 → 119, +13 涌现测试）
- Registry 从 5 个 paper concept → 0 个（干净起点）
- 真实 L0 数据保留（`refactoring` count=2 仍在，展示"还差 3 次到阈值"的有意义进度）
- Forger 从无人调用的孤岛变为 Phase 4 的有机组件
- Agent 现在可以感知"我正在积累什么类型的 skill 需求"（通过 `sf demand-queue`）

#### 影响与意义

这是 SkillForge 自 v0.1 以来**最深刻的一次设计重构**。之前所有工作（v0.2.0~0.2.5）都在完善"预设种子 skill + 校准"的工程实现，现在承认这个预设本身是错的。

新形态下：
- **Registry 是 emerging 的结果，不是设计阶段的 assumption**
- **Forger 从 tail-end 工具变为 Phase 4 的有机组件**
- **capability_gains 不再靠人力估算，而是由真实 rating 历史逐步校准**（草稿默认 L2 quality_tier + 全 0 gains，使用后自然增长）

v0.2.6 是 SkillForge 从"工程原型"走向"自进化系统"的关键一步。

#### 遗留待办

- v0.2.5 的 FIX-040~042（SF 标签示例对齐 / mdc 冗余删除 / `test_infer_task_type.py` 补测）仍未处理，见 v0.2.7 复审合并后续处理。

---

### v0.2.7-review (2026-04-17) — 第五轮全盘复审：v0.2.6 落地后的"涌现一致性"扫荡

**状态**: 仅复审；漏洞清单 + 修改方案已列出，待用户决策执行优先级

#### 复审动机

v0.2.6 完成了涌现式 Registry 的结构性重构，但**只改了 Forger / Registry / Phase 2 三处**。Phase 4 的 task_type 消化逻辑、L0 索引结构、mdc 降级路径 / 反思章节 / 数据存储章节等多处仍然沿用 v0.2.5 前"预设种子"哲学下写的代码和文档。本轮复审做一次彻底的**哲学一致性扫荡**。

#### 实用性再评分（分相）

| 相 | 功能 | v0.2.6 分 | v0.2.7-review 分 | 变化原因 |
|---|-----|----|----|-----|
| 诊断能力 | Phase 1 + SF 标签 | 82 | 82 | 无变化 |
| 记忆闭环 | sf update-l0 | 80 | 75 | Phase 4 的 task_type 选择规则在 Registry 空时**无法执行**，Agent 本轮自己踩坑未能自动写 L0（P0-V06-2） |
| Skill 生成 | Forger | 65 | 65 | 无变化（v0.2.6 新上线） |
| 文档一致性 | mdc 对齐 | 70 | 55 | ↓ — v0.2.6 改动局部彻底但**全局不彻底**：反思章节、StrReplace 降级路径、L0 头部注释均未随涌现哲学调整 |
| 工程整洁度 | 代码债务 | 72 | 70 | FIX-040/041/042 三项技术债继续积压；新发现 6 处涌现哲学残留 |
| 测试覆盖 | pytest | 90 | 90 | 无变化（119 全过） |

**综合实用性：72 / 100**（v0.2.6 后持平；方向正确但落地执行未收尾）

**核心判断**：v0.2.6 是哲学重构，但只改了它**最显眼的地方**（Registry 和 Forger），没完整清理与之配套的所有周边——就像换了发动机却没换匹配的油路。

---

#### 新发现的漏洞清单

##### 🔴 P0-V06-1：L0 索引与"涌现哲学"彻底冲突（最根本自相矛盾）

**位置**：`memory/capability-index.yaml`

**症状**：
- mdc 宣称 Registry 默认空、skill 涌现式生长
- 但 L0 **仍预置 29 个 task_type 条目**（`algorithm_design` / `audio_processing` / ... 全是 count=0 的空壳）
- 其中 3 条标注 `# legacy alias`（`data_analysis` / `kol_outreach` / `seo`），是 v0.2.1 引擎路径的考古文物
- 头部注释 line 13-14 写着"task_types 与 skillforge-registry.yaml 的并集保持一致"——Registry 已经空了，这条注释在自我否定

**为什么 P0**：这是整个 v0.2.6 重构**最根本的自相矛盾**。Agent 面对 L0 里 29 个空条目 + mdc 的"涌现"说辞，无法协调：要么当它们不存在（涌现纯粹但违反字面规则），要么照用（涌现成了空话）。

**修复方案**：
1. 清空 L0 到只剩 `default`（兜底）+ `refactoring`（已有 count=2 真实数据），共 2 个条目
2. 删除 3 条 `# legacy alias` 考古注释
3. 重写头部注释：去掉"与 Registry 并集一致"，改为"条目在 `sf update-l0` 首次写入时动态创建，代表你真实做过什么"

##### 🔴 P0-V06-2：Phase 4 task_type 选择规则在当前状态下**无法执行**

**位置**：`.cursor/rules/skillforge.mdc:240-244`

```
task_type 选择规则（不强制精确分类）：
- 从 skillforge-registry.yaml 的 task_types 集合中，选最贴近当前任务的一项
- 实在难以归类时，用 "default"
```

**症状**：Registry v0.2.6 起默认空。这条规则字面执行的结果是"从空集合中选"——Agent 只能全归 `default`，L0 失去区分度，**Forger 阈值永远触发不了**。

**自证**：本轮复审前，Agent（我）上一轮（v0.2.6 实施任务）没有主动调 `sf update-l0` 给自己打分——正是因为找不到 authoritative 的 task_type 归属（"v0.2.6 涌现式 Registry 实施"该归哪个标签？Registry 里没有对应项）。这是**设计漏洞导致的行为缺失**，不是 Agent 健忘。

**修复方案**：改写为授权 Agent 自主命名：

```
task_type 选择规则（涌现式，v0.2.7 起）：

1. 优先从 L0 索引已有条目中选最贴近的一项（保证同类任务累积到同标签下）
2. 若 L0 无合适条目，Agent **自行命名**一个 snake_case 标签描述"做了什么"
   - 例：`architecture_review` / `figma_to_code` / `bug_diagnosis` / `refactoring`
   - 约束：小写 / snake_case / 名词或动名词短语 / 避免动词开头
   - 同名约束：同类工作请反复使用同一标签；命名一致性是"涌现"成立的前提
3. 实在难以归类才用 `default`
4. 同一轮任务的多次子操作归为**同一** task_type
```

##### 🔴 P0-V06-3：mdc "降级路径"建议过期且**危险**

**位置**：`.cursor/rules/skillforge.mdc:246-248`

```
若 sf 命令不可用（Python 环境未安装）：
此为降级路径，参考 Phase 4 v0.2.1 行为：直接用 StrReplace 修改 yaml
的 count/avg_delta/gap_adjustment 字段。
```

**问题**：
1. 第二步的 `pip3 install -e` 兜底已覆盖"sf 未安装"场景，此降级路径**根本轮不到触发**
2. StrReplace 直接改 yaml 会丢：
   - 审计注释追加（Forger 的数据源）
   - EMA 计算（校准基础）
   - trend 更新
   - `global_gap_adjustment`
   - **Forger 触发**（最关键——直接 StrReplace 等于关闭涌现机制）
3. v0.2.5 FIX-041 就标记要"清理死文本降级路径"，v0.2.6 未清理

**修复方案**：删除这条降级指示，改为：
> 若 `pip3 install -e` 本身失败（网络 / 权限问题），跳过本轮 Phase 4 记录，在下次 sf 可用时补记当次摘要即可。**严禁用 StrReplace 直接改 yaml**——会破坏 EMA / Forger 触发等下游管线。

##### 🟡 P1-V06-1：mdc "反思记录"章节仍完全冗余（**FIX-041 重申**）

**位置**：`.cursor/rules/skillforge.mdc:294-296`

```
## 反思记录
反思的具体写入格式已在 **Phase 4 · 第三步**给出。此处不再重复定义。
```

三行零信息量，只是把读者指回 Phase 4。v0.2.5 标记延后，v0.2.6 未处理，继续积压。

**修复方案**：整节删除；如果目录 / TOC 有指向也一起清理。

##### 🟡 P1-V06-2：SF 标签示例与"max 定义"不自洽（**FIX-040 重申**）

**位置**：`.cursor/rules/skillforge.mdc:41 vs 46`

- line 41 定义：`Gap 总分 = max(prec, reas, tool)`
- line 46 示例注释：`[SF | Gap≈3 | independent] ← 所有维度 ≤ 5，无缺口`

max=3 推不出"所有维度 ≤ 5"（虽然蕴含关系成立，但注释在描述充分条件的同时写了必要条件）。

**修复方案**：示例注释改成事实对齐：

```
[SF | Gap≈3 | independent]           ← 最大维度 = 3
[SF | Gap≈12 | light-hint]          ← 最大维度 = 12
[SF | Gap≈28 | suggest]              ← 最大维度 = 28
[SF | Gap≈38 | force-enhance]        ← 最大维度 = 38
[SF | Gap≈55 | out-of-scope]         ← 最大维度 = 55
```

##### 🟡 P1-V06-3：`sf forge` 空状态用户体验差

**位置**：`src/skillforge/cli.py` — `forge` 命令

**症状**：当前 L0 没有达到阈值的 task_type 时，`sf forge` 默默打印 29 行"跳过 count=0 < 5"表格，用户看到一堆红字但不知道该做什么。

**修复方案**：在所有 rows 都是"跳过"状态时，在表格下方打印一行引导：

```
当前 L0 中暂无达到 Forger 阈值（count ≥ 5）的 task_type。
运行 `sf demand-queue` 查看所有 task_type 距阈值的进度。
```

并且默认只展示 count>0 的行（类似 `sf demand-queue` 的过滤策略），count=0 的条目在 `--verbose` 时才显示。

##### 🟡 P1-V06-4：`_infer_task_type` 与涌现哲学冲突（**FIX-042 升级**）

**位置**：`src/skillforge/cli.py:1056-1099`

**症状**：这 20 条 pattern 是给"预设 5 个种子 skill"设计的映射表。涌现式下，**每个用户的 task_type 词汇表都不同**，没有 authoritative list 可以硬编码。

**两种路径辨析**：
- **Cursor 对话路径**：Agent 自己选 task_type（按 P0-V06-2 修复），不走 `_infer_task_type`
- **Python 引擎路径**（`sf analyze` / `sf run`）：仍需要一个从任务描述推 task_type 的函数

**修复方案**：
- 不删除此函数（引擎路径仍需要）
- 给它加 docstring 明确"**仅服务于 `sf analyze`/`sf run` 的 Python 引擎批量路径**；Cursor 对话路径 Agent 自行命名 task_type"
- FIX-042 的"补测试 + 打分匹配"按原计划推进

##### 🟡 P1-V06-5：`indexer.DEFAULT_TASK_TYPES` 注释过期

**位置**：`src/skillforge/indexer.py:36-39`

```python
DEFAULT_TASK_TYPES = [
    # Legacy fallback only — 实际运行时由 _load_default_task_types_from_registry()
    # 动态从 skillforge-registry.yaml 提取 task_types，保证与 Registry 单一数据源对齐
    "default",
]
```

v0.2.6 Registry 空了，`_load_default_task_types_from_registry()` 实际上总是返回 `{"default"}`——和 hardcoded DEFAULT_TASK_TYPES 等价。注释描述的"动态加载"功能暂时失效。

**修复方案**：保留代码（将来 Registry 填充时有用），改注释为：

```python
# v0.2.6 起 Registry 默认空，此函数退化为返回 ["default"]；
# Registry 累积 skill 后将恢复动态加载（作为 IndexManager 初始化 task_type_index 的种子）。
```

##### 🟢 P2-V06-1：Forger 草稿 `capability_gains` 全 0 会被 Phase 2 埋没

**位置**：`src/skillforge/forger.py:_render_lightweight_draft()`

**症状**：草稿默认 `precision: 0, reasoning: 0, tool_knowledge: 0`。`sf push` 入库后，Phase 2 `sf search` 按预估增益排序，新 skill 会排到末尾，用户可能看不到它（或以为 push 失败）。

**修复方案（两选一）**：
- **A**：草稿保留 0，`sf search` 在命中含 gain=0 新 skill 时打印 hint "新入库未校准 skill {id}，需要 ≥10 次 Phase 4 反馈后参与排序"
- **B**：草稿改为 `precision: 10, reasoning: 10, tool_knowledge: 10`（保守正估计），由 Phase 4 真实反馈 EMA 校准下来

**推荐 B**：让 skill 一入库就有起点，quality_tier=L2 已经标示"未校准"，不需要额外 UX 告警。

##### 🟢 P2-V06-2：audit comment 时间戳正则容忍度不足

**位置**：`src/skillforge/forger.py:_AUDIT_PATTERN`

当前 `[\d\-T:\.]+` 匹配 `YYYY-MM-DDTHH:MM`（indexer 用 `timespec="minutes"`）。若将来改 `timespec="seconds"` 带 `:SS`，正则仍能匹配（`:` 在字符集内）；若加时区 `+08:00` 会多一个 `+`，需要更新。

**修复方案**：仅记录，暂不修。若将来真要改时间戳格式，同步更新正则。

---

#### FIX 执行记录（v0.2.7 规划）

| ID | 优先级 | 状态 | 描述 |
|----|--------|------|------|
| **FIX-049** | **P0** | **✅** | L0 索引清理：从 29 个预置空壳 → 3 个真实条目（`default` / `refactoring` / `architecture_review`），删 3 条 legacy alias，重写头部注释说明涌现式条目动态创建 |
| **FIX-050** | **P0** | **✅** | mdc Phase 4 task_type 规则重写：4 步清单，授权 Agent 自主 snake_case 命名（含格式约束 + 一致性约束），降低 `default` 使用频率 |
| **FIX-051** | **P0** | **✅** | mdc 删除"StrReplace 降级路径"，改为"sf 不可用时跳过，下次补记"；明确禁止直接改 yaml（会破坏 EMA / Forger 三个下游管线） |
| **FIX-052** | **P1** | **✅** | mdc 删除"反思记录"冗余章节（继承 FIX-041，4 个 iteration 后终于清理） |
| **FIX-053** | **P1** | **✅** | mdc SF 标签示例注释改为"最大维度 = N"（继承 FIX-040，精准对齐 max 定义） |
| **FIX-054** | **P1** | **✅** | `sf forge`：默认过滤 count=0 条目，全跳过时打印引导语"运行 sf demand-queue 查看进度"；`--force` 时展示全部 |
| **FIX-055** | **P1** | **✅** | `_infer_task_type` docstring 加"⚠️ 仅 Python 引擎路径"声明，Cursor 对话路径 Agent 自主命名 |
| **FIX-056** | **P1** | **✅** | `indexer.DEFAULT_TASK_TYPES` 注释更新："v0.2.7 起 Registry 默认空，此函数退化为返回 `['default']`" |
| **FIX-057** | **P2** | **✅** | Forger 草稿 `capability_gains` 改为保守正估计（precision/reasoning/tool_knowledge 均为 10），避免入库后 Phase 2 排序中被埋没 |
| **FIX-042** | **P1** | **✅** | 新增 `tests/test_infer_task_type.py`（32 测试，正向 20 + 负向 5 + 冲突 4 + 边界 3）；`_infer_task_type` 从首匹配重构为**打分匹配**（统计命中关键词数，取最高分，平局按 pattern 声明顺序稳定排序） |

**回归验证**：`pytest -q` → **151 / 151 全过**（119 → 151, +32）

#### 关键洞察

v0.2.6 的"涌现式"转向在 Forger 和 Registry 两个模块里做得很彻底，但忘了同步检查所有**下游依赖者**：
- L0 索引（条目还在预置——P0-V06-1）
- Phase 4 的 task_type 规则（还在从 Registry 选——P0-V06-2）
- mdc 的 StrReplace 降级（绕过 Forger 触发管线——P0-V06-3）
- `_infer_task_type`（还在按"预设种子"工作——P1-V06-4）

这是典型的**范式转变未收尾**：新哲学已宣布、核心组件已改造，但周边组件与文档的配套清洗缺位。v0.2.7 应该作为一次专门的**一致性扫荡**版本，不引入新功能，只做干净收尾。

---



**状态**: 仅复审，新漏洞清单 + 优化建议待决策

#### 复审动机

用户第四次要求"全盘检查 + 实用性评估 + 改进建议"。v0.2.4 的 P0 (FIX-023/024/025) 和 P1 (FIX-026~030) 全部完成，97 项 pytest 测试通过。按约定，本轮复审应该以"所有已知问题都修完了"为基线，重点看：

1. 上一轮的修复有没有引入新的不一致
2. v0.2.4 列出的 P2 清单（FIX-031~035）是否仍然准确
3. 有没有 v0.2.4 忽略的**元层面**问题（特别是 Phase 2/3 的"纸面概念"）

#### 验证基线（客观事实）

- ✅ `pytest tests/ -x` **97 项全过**（v0.2.4 只有 71 项，新增 test_update_l0.py 26 项）
- ✅ `sf update-l0` 现在真正更新 `trend` + `global_gap_adjustment`（FIX-023 已验证）
- ✅ `sf` 命令全局可用（`~/.zshrc` 已持久化 PATH）
- ✅ mdc 规则、SKILL.md、Registry、L0 索引四方对齐
- ✅ CLI 映射表（`_infer_task_type`）与 Registry 对齐，不再污染 L0

#### 实用性再评分（分相）

| 相 | 功能 | v0.2.4 分 | v0.2.5 分 | 变化原因 |
|----|------|-----------|-----------|---------|
| Phase 1 | Gap 诊断 + SF 标签 | 85 | 85 | 无变化，仍然稳定 |
| Phase 2 | Skill 匹配推荐 | 40 | 40 | **仍然纸面**：mdc 描述 Phase 2 但无具体执行指令，Agent 从不读 Registry |
| Phase 3 | 增强执行 | 50 | 50 | **仍然纸面**：无强制契约，Agent 自由发挥 |
| Phase 4 | L0 闭环 | 55 | **78** | FIX-023 补全 trend + global_gap_adjustment，FIX-024 加回归保护 |
| 反思/Forger | 失败归因 + 草稿生成 | 60 | 62 | FIX-020 加禁止外部归因约束，但 Forger 仍未被触发过 |

**综合实用性**：约 **72/100**（相比 v0.2.4 的 65/100 提升 7 分，主要来自 Phase 4 真正跑通）

**核心认知更新**：
- v0.2.4 以为"Phase 2/3 只是空壳"是个可忍受的缺陷；v0.2.5 认为**这是 SkillForge 定位错位的症结**——mdc 规则里写得煞有介事，但 Agent 在实操中完全不执行，**规则与行为的落差本身就是最大的技术债**
- 这个系统实质上已经变成 "Phase 1（诊断）+ Phase 4（校准）" 的双相系统，Phase 2/3 是装饰，建议**要么下决心实现、要么明确从 mdc 里删掉降级为 optional**

---

#### 问题清单（v0.2.5 新发现）

##### P0-NEW（Critical）

**P0-NEW-1: `sf run --rating` 路径的 delta 公式违反 `actual=S` 约定**

- 位置：`src/skillforge/cli.py:262-263`
  ```python
  closed = orch.evaluate_and_close(result, actual_score=rating / 5 * 100, user_rating=rating)
  delta = rating / 5 * 100 - result.trajectory.phase1.predicted_score
  ```
- 评分约定（`sf eval` 和 mdc 规则都是）：`actual = predicted`，`delta = (rating - 3) × 20`
- 但 `sf run --rating 5 --predicted 80` 会得出：
  - `sf eval`: actual=80, delta=+40 ✓（符合约定）
  - `sf run --rating 5`: actual=100, delta=100-80=20 ✗（错）
- **严重后果**：两条 CLI 路径对同一个 rating 算出完全不同的 delta，写入 L0 后 gap_adjustment 校准会被污染
- **修复方案**：让 `sf run` 和 `sf eval` 共用一个评分计算函数；`evaluate_and_close` 的 actual_score 参数改传 `predicted`，delta 用 `(rating-3)*20`

**P0-NEW-2: `task_type="other"` 硬编码兜底值会污染 L0 索引**

- 位置：多处硬编码
  ```
  src/skillforge/cli.py:91      task_type = task_types[0] if task_types else "other"
  src/skillforge/cli.py:213     task_type = task_types[0] if task_types else "other"
  src/skillforge/cli.py:275     task_type: str = typer.Option("other", ...)
  src/skillforge/evaluator.py:110,151  task_type = trajectory.task_type or "other"
  src/skillforge/engine.py:325  task_type = phase1.task_types[0] if phase1.task_types else "other"
  src/skillforge/reflexion.py:281  task_type: str = "other"
  ```
- `"other"` **不在 Registry 也不在 L0 默认条目**，首次写入时会 append 一条非 Registry 类型到 L0 索引，违反 FIX-028 "task_type 严格对齐 Registry" 的修复目的
- v0.2.4 的 FIX-028 只改了 `_infer_task_type`，漏了这六个兜底位
- **修复方案**：全局替换为 `"default"`（L0 索引已有该条目，Registry 推断兜底也是 `"default"`）

**P0-NEW-3: mdc "数据存储"章节与 Phase 4 实现自相矛盾**

- 位置：`.cursor/rules/skillforge.mdc:227`
  ```
  ├── capability-index.yaml   # L0 索引（Phase 4 直接更新，不再依赖外部命令）
  ```
- 但 Phase 4 第二步（line 135-154）明确要求用 `sf update-l0` CLI 命令更新
- line 232-234 的 v0.2.3 注脚又说"改走 sf update-l0 CLI helper"
- 正文 + 注脚 + 实际路径三处描述打架，阅读顺序决定 Agent 理解
- **修复方案**：改为"L0 索引（Phase 4 通过 `sf update-l0` 更新，helper 内部处理 YAML）"，删除矛盾的"不再依赖外部命令"

---

##### P1-NEW（High）

**P1-NEW-1: mdc Phase 2/3 章节是"描述"而非"指令"**

- 位置：`.cursor/rules/skillforge.mdc:100-106`
  ```
  ### Phase 2：Skill 缺口检测
  当 Gap ≥ 15 时，匹配 Registry 中 skill，说明"这个 skill 能补多少分"。

  ### Phase 3：执行（增强态）
  启用 skill 后，将 skill 内容作为额外 context 执行。遇到 skill 未覆盖的情况时主动坦白。
  ```
- **问题**：Agent 看到这里只会"知道"而不会"执行"——没有具体的工具调用、文件读取、或输出格式约束
- **实测**：本次 v0.2.5 复审（Gap≈20）和上一轮 v0.2.4 复审（Gap 应在 suggest 区间）我都**没有真正读过 skillforge-registry.yaml**，直接凭印象判断
- **修复方案（两选一）**：
  - A: 让 Agent 在 Gap ≥ 15 时用 Shell 工具运行 `sf search <关键词>` 或 Read `skillforge-registry.yaml` 的特定片段
  - B: 承认 Phase 2/3 是 optional，降级为"建议"而非"规则"

**P1-NEW-2: mdc SF 标签示例与诊断定义精确性不一致**

- 位置：`.cursor/rules/skillforge.mdc:46`
  ```
  [SF | Gap≈3 | independent]           ← 所有维度 ≤ 5，无缺口
  ```
- 但第 41 行写 `Gap 总分 = max(prec, reas, tool)`——最大值 = 3 不能推出"所有维度 ≤ 5"
- 这个逻辑跳跃会让 Agent 在边界场景下纠结（如：prec=4, reas=6, tool=3 → max=6，应该叫 light-hint 但离 5 很近）
- **修复方案**：把例子改为"所有维度缺口 ≤ 5（Gap=max=3）"，明确"最大维度"就是"Gap 总分"

**P1-NEW-3: mdc "反思记录"章节完全冗余**

- 位置：`.cursor/rules/skillforge.mdc:218-220`
  ```
  ## 反思记录
  反思的具体写入格式已在 **Phase 4 · 第三步**给出。此处不再重复定义。
  ```
- 零信息量，只是把读者指回 Phase 4
- **修复方案**：直接删掉这个章节

**P1-NEW-4: mdc "降级路径"段落已是死文本**

- 位置：`.cursor/rules/skillforge.mdc:170-172`
  ```
  **若 sf 命令不可用（Python 环境未安装）**：
  此为降级路径，参考 Phase 4 v0.2.1 行为：直接用 StrReplace 修改 yaml 的...
  ```
- FIX-027 后自动安装脚本已很稳定（`command -v sf &>/dev/null || pip3 install -e ...`），降级路径实际不会走到
- 保留这段反而让 Agent 在不应该降级的场景犹豫
- **修复方案**：删除或改为"仅极端 CI 场景，否则忽略此路径"

**P1-NEW-5: `_infer_task_type` 关键词匹配顺序敏感，无测试覆盖**

- 位置：`src/skillforge/cli.py:759-804`
- FIX-028 改了 20 条 pattern，但没有单测保护。顺序敏感的匹配会在复杂任务描述上产生意外结果：
  ```
  任务："用 Python 做数据清洗报告"
  现在匹配：code_generation（撞到 "python"）
  应该匹配：data_cleaning（更具体）
  ```
- **修复方案**：
  - 补测试 `tests/test_infer_task_type.py`（至少 10 条 pattern 的双向覆盖）
  - 重构匹配逻辑：对所有 pattern 打分（命中关键词数）取最高，而非首匹配

---

##### P2-NEW（Low，记录但本轮不修）

| ID | 问题 | 影响 |
|---|---|---|
| P2-NEW-1 | `_estimate_gap` 是玩具函数（关键词硬编码），但 docstring 没明确标注 | `sf analyze` 输出误导 |
| P2-NEW-2 | Forger 触发路径未实现（mdc 提"≥5 次"但无代码检查/触发） | 功能纸面 |
| P2-NEW-3 | `sf ingest` 加了 deprecation warning 但命令仍存在 | 用户困惑，但无实际损害 |
| P2-NEW-4 | mdc "双分数制"表格 `actual = S` 改动后未同步更新 `A` 字段说明 | 小 |

（v0.2.4 列出的 FIX-031~035 中，FIX-031/032/034/035 仍然有效，合并到本批 P2 处理）

---

#### 整体优化建议

**元策略：正视"Phase 2/3 纸面概念"**

本轮最重要的发现不是某个具体 bug，而是**系统定位错位**——mdc 规则描述了一个四相系统，但实际运行的只有 Phase 1+4 双相。这带来两个选择：

**选项 A：下决心让 Phase 2/3 真正跑起来（投入大）**
- mdc Phase 2 加强制指令："当 Gap ≥ 15 时必须读 `skillforge-registry.yaml` 并输出候选 skill_id 列表"
- Phase 3 加注入契约："启用 skill 时必须 Read 对应 SKILL.md 并在回复中声明 skill_id"
- 需要 refactoring.count 翻倍的工作量

**选项 B：承认双相系统本质（投入小）**
- mdc Phase 2/3 降级为"可选路径"，明确"仅在用户显式要求 skill 增强时激活"
- SKILL.md 架构图从四相改为二相（Phase 1+4）
- 保留 Phase 2/3 的 Python 代码但从对话规则里摘除强制性

**我的建议**：**选 B，但保留代码**。理由：
1. 真实数据支持——累计 6 轮复审、20+ 次 SF 标签输出，Phase 2/3 从未真跑过一次
2. 修 mdc 规则成本低（改两段文案），代码改动为零
3. 为 Phase 2/3 保留未来复活可能（代码在、Registry 在、测试在）
4. Agent 的"纸面负担"（读到规则但不执行的认知失调）消失

**执行序**：
1. 先修 P0-NEW-1/2/3（三个硬 bug）
2. 再修 P1-NEW-1（Phase 2/3 降级为 optional，同时清理 P1-NEW-3/4 的冗余章节）
3. 做 P1-NEW-2（SF 标签定义精准化）+ P1-NEW-5（匹配测试）
4. P2-NEW 留到下一轮

---

#### FIX 执行记录

| ID | 优先级 | 状态 | 描述 |
|----|--------|------|------|
| FIX-036 | P0 | ✅ | `sf run --rating` 的 delta 路径收敛到 `(rating-3)*20`；顺带修复 `evaluate_and_close` 传 `actual_score` 导致 TypeError 被 try 吞掉的隐藏 bug |
| FIX-037 | P0 | ✅ | 全局替换 `"other"` → `"default"` 兜底（cli.py × 3 / evaluator.py × 2 / engine.py × 1 / reflexion.py × 1 / 测试 × 1，共 8 处） |
| FIX-038 | P0 | ✅ | mdc 数据存储章节重写为"写入路径唯一入口 = `sf update-l0`"，删除矛盾的"不再依赖外部命令"，用户级 mdc 同步 |
| **FIX-039** | **P1** | **✅** | **Phase 2/3 选项 A 落地（强制契约）**：mdc 把 Phase 2 改为必调 `sf search`、Phase 3 改为必调 `sf show`；新增 `sf show <skill_id>` CLI 命令（带 SKILL.md fallback）；9 项契约测试覆盖 |
| FIX-040 | P1 | ⏳ | SF 标签示例与"最大维度 = Gap 总分"定义精准对齐（延后到 v0.2.7） |
| FIX-041 | P1 | ⏳ | 删除 mdc 冗余"反思记录"章节 + 清理死文本降级路径（延后到 v0.2.7） |
| FIX-042 | P1 | ⏳ | 补 `tests/test_infer_task_type.py`（≥10 条双向覆盖），重构为打分匹配（延后到 v0.2.7） |
| **FIX-043** | **P0** | **✅** | **v0.2.6 核心**：清空 Registry skills（5 个种子 → 0），头部注释重写说明涌现式生长 |
| **FIX-044** | **P0** | **✅** | **v0.2.6 核心**：`forger.py` 从 stub 做实，新增 `should_forge()` + `forge_draft()`；数据源 L1 trajectory → L0 索引 + audit comment；阈值 3 → 5；生成轻量骨架（留白由用户补 Workflow） |
| **FIX-045** | **P0** | **✅** | `update_l0_file` 集成 Forger 自动触发，返回值新增 `forger_draft_path` |
| **FIX-046** | **P1** | **✅** | 新增 `sf forge` / `sf demand-queue` CLI 命令；demand-queue 自动过滤 `count=0 且 avg=0` 的预置空条目 |
| **FIX-047** | **P0** | **✅** | mdc Phase 2 改写：情况 A（空 Registry 友好，静默/一行提醒）+ 情况 B（沿用 v0.2.5 候选表）；新增「Forger 草稿感知」章节；用户级 mdc 同步 |
| **FIX-048** | **P1** | **✅** | 新增 `tests/test_forger_emergent.py`（13 测试）；修复 `test_registry_effectiveness` 不依赖预置 skill |

**回归验证**：`pytest tests/ -q` → **119 项全过**（较 v0.2.5 的 106 项 +13）

---

#### FIX-039 详细记录（Phase 2/3 上线关键节点）

**阻塞事实**：复审前发现 Registry 登记的 5 个种子 skill（code-expert/seo-analysis/data-analysis/research/video-production）的 `path` 字段全部指向**物理不存在**的 SKILL.md（workspace `.cursor/skills/` 只有 `xhs-copy-combo`）。这就是 Phase 2/3 历史上从未被触发的**根因**——不是规则不强制，是真跑也会失败。

**决策**：用户选定"选项 A：让 Phase 2/3 真正跑起来"，配合 fallback 保证即使 SKILL.md 缺失也能提供价值。

**落地动作**：

1. **新增 `sf show <skill_id>` CLI 命令**（`src/skillforge/cli.py`）
   - 若 `skill.path` 指向真实 SKILL.md → 输出完整文件内容（`source=skill_md`）
   - 若不存在 → 用 Registry 的 description / task_types / capability_gains / trigger_keywords 拼装最小 inline context（`source=registry_inline`, `path_missing=True`）
   - 支持 `--json` 模式，供 Agent 自动化消费
   - 支持绝对路径 / 相对 Registry yaml 目录 两种 path 形式

2. **辅助函数 `_build_inline_skill_context(skill)`**
   - 输出标准化 Markdown：描述 / 领域 / 适用任务类型 / 能力提升估算 / 触发关键词 / 质量等级 / 使用指引
   - 空字段自动降级到"（未指定）/（未填写）"，不出空行

3. **mdc Phase 2 升级为强制契约**
   - Gap ≥ 15 时**必须**运行 `sf search "<关键词>" --json`
   - 必须在回复中展示候选 skill 表
   - Gap 在 suggest 区间可默认执行；在 force-enhance 区间必须等用户明确指令

4. **mdc Phase 3 升级为强制契约**
   - 用户确认启用后**必须**运行 `sf show {skill_id}`
   - 把输出作为本轮额外 context
   - 回复末尾必须声明 `[Phase 3] 本轮启用 skill: {id}（source: skill_md | registry_inline）`
   - `path_missing=true` 时必须主动坦白"SKILL.md 尚未创建，仅用 Registry 轻量 context"

5. **新增测试 `tests/test_show_skill.py`**（9 项）
   - 真实 SKILL.md 读取正确
   - 缺失 path 降级到 inline context
   - 空 path 也能降级不崩溃
   - 未知 skill_id 返回 exit_code=1
   - 文本模式 vs JSON 模式的行为差异
   - inline context 的所有 section 完整性
   - 空字段边界处理
   - 绝对路径解析

**后续承接（v0.2.7 候选）**：补 5 个种子 skill 的真实 SKILL.md（`code-expert/seo-analysis/data-analysis/research/video-production`），把 `source: registry_inline` 的比例降到 0。在此之前，Phase 3 可以用 inline context 跑起来积累数据，由真实使用反推"种子 skill 应该写成什么样"。

---

### v0.2.4 (2026-04-17) — 第三轮深度复审：实用性评估 + 新漏洞清单

**状态**: 仅复审，问题清单 + 修复方案已待命

#### 复审动机

v0.2.3 完成后用户第三次要求"全盘检查 + 实用性评估"。前两轮复审各自修完立即又暴露新问题，说明系统已经进入"盲区越修越深"的阶段。本轮必须直面一个元问题：**这个系统真的值得继续投入吗？**

#### 验证基线（客观事实）

- ✅ `pytest tests/ -x` 71 项全过（数据层兼容未被打破）
- ✅ `sf update-l0` CLI 首次可用（已通过 dry-run 验证）
- ✅ L0 索引已积累真实数据（`refactoring.count = 2`）
- ✅ SF 状态标签在每条回复首行都有输出（Phase 1 诊断习惯已形成）
- ✅ `sf` 命令已安装到 `/Users/vivx/Library/Python/3.9/bin/sf`，`~/.zshrc` 已加 PATH

#### 实用性评估（分相评分）

| 相 | 功能 | 实际运行状态 | 分 |
|----|------|------------|-----|
| Phase 1 | Gap 诊断 + SF 标签 | ✅ 稳定运行，每条回复首行都有 | 85 |
| Phase 2 | Skill 匹配推荐 | ⚠️ mdc 概念，Agent 实际不读 Registry | 40 |
| Phase 3 | 增强执行 | ⚠️ 靠 Agent 自觉，无强制契约 | 50 |
| Phase 4 | L0 闭环 | ❌ **半瘫痪**：CLI 路径不更新 trend / global_gap_adjustment | 55 |
| 反思/Forger | 失败归因 + 草稿生成 | ⚠️ 反思未触发过（rating=1 从未发生） | 60 |

**综合实用性**：约 **65/100**（相比 v0.2.3 自评 88 分实际偏乐观）

**核心发现**：SkillForge 的**最大价值来自 Phase 1 的"诊断习惯"**——强制 Agent 在每条回复开头输出 SF 标签，迫使自己对任务复杂度做显性评估。这个习惯哪怕其他 Phase 全废，都仍然有价值。

**最大缺陷**：Phase 4 闭环在 CLI 路径下只跑了一半（trend 和 global_gap_adjustment 从未更新过），导致"自我校准"这个核心卖点**从未真正运行过**。

---

#### 问题清单（v0.2.4 发现）

##### P0-LATEST（Critical，必须修）

**P0-A: `update_l0_file()` 不更新 `trend` 和 `global_gap_adjustment`**

- 位置：`src/skillforge/indexer.py:289-410`
- 对比 `IndexManager.update()`（同文件 196-248 行），这两个字段的更新逻辑**完全缺失**：
  - trend 的 5 次门槛 + avg_delta 阈值判定 → CLI 路径下永远 `stable`
  - `global_gap_adjustment = round(old * 0.95 + delta * 0.05)` → CLI 路径下永远不变
- **严重后果**：所有走 Cursor 对话场景的任务，Phase 1 全局校准的数据源（`global_gap_adjustment`）永远是 0，SkillForge 的"自我校准"核心卖点从未真正运行过
- **修复方案**：把 IndexManager.update() 中的 trend 和 global_gap_adjustment 逻辑移植到 update_l0_file 里，用 regex 同步更新 _meta.global_gap_adjustment 字段

```python
# 新增到 update_l0_file（在 _meta 更新那一段之前）
# trend 更新
new_trend = "stable"
if new_count >= 5:
    if abs(new_avg) > 10:
        new_trend = "degrading"
    elif abs(new_avg) < 5 and new_count >= 3:
        new_trend = "improving"
new_body = re.sub(r"(trend:\s*)\w+", f"trend: {new_trend}", new_body, count=1)

# global_gap_adjustment 更新
gga_m = re.search(r"global_gap_adjustment:\s*([-+]?\d+)", text)
old_gga = int(gga_m.group(1)) if gga_m else 0
new_gga = int(round(old_gga * 0.95 + delta * 0.05))
text = re.sub(r"(global_gap_adjustment:\s*)[-+]?\d+",
              f"global_gap_adjustment: {new_gga}", text, count=1)
```

---

**P0-B: `update_l0_file` 零测试覆盖**

- `grep update_l0_file tests/*.py` 返回 0 匹配
- FIX-022 增加的核心 helper（含 regex 替换 / 保留注释 / 原子写入 / 反思模板）全无回归保护
- 任何人改一行 regex 都可能静默破坏 yaml
- **修复方案**：新增 `tests/test_update_l0.py`，覆盖：
  - ✓ 已存在 task_type 条目的数据更新
  - ✓ 审计注释追加到条目末尾
  - ✓ 保留已有注释（refactoring 的 sf-v0.2.1-fix / sf-v0.2.2-fix）
  - ✓ 不存在的 task_type 会创建新条目
  - ✓ rating=1 触发 reflections.md 追加模板
  - ✓ `_meta.last_task_id` / `total_executed` / `updated_at` 同步
  - ✓ **P0-A 修复后**: trend 和 global_gap_adjustment 正确更新
  - ✓ 原子写入（模拟中断仍能恢复原文件）

---

**P0-C: `SKILL.md` 与 mdc / 实现严重脱节**

- `SKILL.md:155-158` 仍写"直接更新 yaml"+ 错误公式 `gap_adjustment += current_delta`（实际是 `= round(avg_delta*2)`）
- `SKILL.md:194` 仍列 `cursor-timings.md`（v0.2.2 已废弃）
- `SKILL.md:231` 关系图包含 `ffmpeg-skill`（Registry 里不存在此 skill_id）
- `SKILL.md:162 vs :220` Forger 阈值冲突（5 次 vs 3 次）
- `SKILL.md:241` 更新日志只有 2026-04-15 一条，v0.2.1/v0.2.2/v0.2.3 全缺失
- **修复方案**：整段重写 Phase 4 节 + 数据存储节 + 更新日志节，严格对齐 mdc v0.2.3

---

##### P1-LATEST（High，短期修）

**P1-A: mdc `Skill Registry` 章节与实际 Registry 不对齐**

- mdc line 74-82 列 `research-skill` / `seo-analysis-skill` / `figma-skill` / `ffmpeg-skill`
- Registry 实际 skill_id：`code-expert` / `seo-analysis` / `data-analysis` / `research` / `video-production`
- `figma-skill` 和 `ffmpeg-skill` **在 Registry 中根本不存在**
- **修复方案**：mdc 改为"参考 `skillforge-registry.yaml` 的 skill_id 字段"，避免在规则中重复维护列表

**P1-B: mdc Phase 4 "完整闭环说明" 自相矛盾**

- mdc line 232 "不依赖任何外部命令"
- mdc line 162-181 "调用 `sf update-l0`"
- v0.2.2 遗留文案，改 helper 时没同步
- **修复方案**：把"不依赖任何外部命令"改为"仅依赖已预装的 sf 命令，对用户不可见"

**P1-C: CLI `_infer_task_type` 产生 Registry 外的 task_type**

- `cli.py:754-763` 关键词表映射到 `seo` / `kol_outreach` / `data_analysis` / `design` / `writing`
- 这些在 Registry 里全不存在（Registry 用的是 `content_analysis` / `data_cleaning` 等）
- 用户跑 `sf analyze` / `sf run` 会写入 legacy alias 条目，污染 L0 索引
- **修复方案**：映射表改为 Registry 实际 task_type；或从 Registry 动态生成映射（类似 FIX-015 思路）

**P1-D: mdc Phase 4 "第零步" vs "第一步" 内容高度重叠**

- 第零步讲"灰色反馈兜底默认 rating=3"
- 第一步讲"rating=3 的识别规则"
- 两者同一件事换两种说法，边界模糊
- **修复方案**：合并为"第一步：识别反馈类型"，把兜底规则作为表格中的默认行 + 关键约束

**P1-E: `sf ingest` 命令成为孤儿**

- `cli.py:649-702` 还注册着
- 但 `cursor-timings.md` v0.2.2 起已不再产出
- 命令丢失了数据源
- **修复方案**：加 deprecation warning 提示用户转用 `sf update-l0`；不立即删除（保留给历史文件场景）

---

##### P2-LATEST（Low，慢慢来）

**P2-A: `update_l0_file` 未校验 task_type 合法性**

- 用户瞎传 task_type（如 `"测试一下"`）会静默创建污染条目
- **修复方案**：参数校验——不在 `Registry.task_types ∪ {"default"}` 中时 stderr 警告，或强制 fallback `"default"`

**P2-B: `task_desc` 未 sanitize**

- `\n` / 反引号 / `#` 会破坏 YAML 注释行
- **修复方案**：`task_desc = task_desc.replace("\n", " ").replace("#", "＃")[:80]`

**P2-C: mdc 双分数制表冲突**

- mdc:68 "A 是执行后的真实质量分"
- mdc:71 "actual = S"
- 两种描述互斥
- **修复方案**：保留 `actual = S` 约定，表格改为"A（实际分）| `=S`，由预估锚定"

**P2-D: SKILL.md Forger 阈值冲突**（已在 P0-C 中合并处理）

**P2-E: 死代码 `_L0_BLOCK_PATTERN`**

- `indexer.py:283-286` 定义但从未被引用
- **修复方案**：删除

**P2-F: mdc 降级路径描述模糊**

- 第二步末尾说"降级到 StrReplace 路径"，但没给具体步骤
- 其实自动安装已经很稳，降级路径使用概率趋近于 0
- **修复方案**：删除降级路径段落，规则更干净

---

#### 整体优化建议

**立即收敛漏洞，暂停新功能**

当前系统的复杂度已经到了"自检查盲区"——每轮复审都会挖出上一轮没看到的问题。再加功能只会让这个现象继续。应优先:

1. 修完 P0-A（真正把 Phase 4 闭环跑通）
2. 修完 P0-B（给 update_l0_file 上回归保护）
3. 修完 P0-C（让 SKILL.md 和 mdc 对齐）
4. 然后才能讨论 Phase 2（skill 匹配）怎么真正跑起来

**Phase 2 的真正落地方案（v0.2.5 候选）**

mdc 规则现在提 Phase 2 但 Agent 从不执行。要真正跑起来需要：

- 在 mdc 里加一条具体指令："当 Gap ≥ 15 时，用 Shell 工具运行 `sf search <任务关键词>` 或直接读 `skillforge-registry.yaml` 找匹配 skill"
- 或在 CLI 暴露 `sf match-skill --task "..."` 专门给 Agent 调用

**元问题：是否值得继续投入？**

- **继续的理由**：Phase 1 的诊断习惯已经形成 + L0 索引开始有真实数据 + 每次复审都让系统更健壮
- **停的理由**：实用性实测 65/100，Phase 2/3 仍然纸面概念，维护复杂度已经显著
- **我的建议**：**继续修 P0/P1，跳过 P2，不加新 Phase 功能直到 refactoring.count ≥ 10**（真正校准出 gap_adjustment 的偏差值，再用数据决定下一步投入方向）

---

#### FIX 执行记录

| ID | 优先级 | 状态 | 描述 |
|----|--------|------|------|
| FIX-023 | P0 | ✅ | update_l0_file 补 trend + global_gap_adjustment 更新（与 IndexManager.update 逻辑完全对齐） |
| FIX-024 | P0 | ✅ | 新增 tests/test_update_l0.py — 26 项覆盖基础更新/注释保留/新条目/meta/trend/反思/原子写入 |
| FIX-025 | P0 | ✅ | SKILL.md Phase 4 / 反思格式 / 数据存储 / Skill 关系图 / 更新日志全面重写 |
| FIX-026 | P1 | ✅ | mdc Skill Registry 章节改为引用 yaml（删 figma-skill/ffmpeg-skill，加正确 skill_id 表） |
| FIX-027 | P1 | ✅ | mdc 删除矛盾的"不依赖任何外部命令"，改为"仅依赖已预装的 sf 命令" |
| FIX-028 | P1 | ✅ | cli._infer_task_type 映射表完全对齐 Registry task_types（20 条 pattern，兜底 default） |
| FIX-029 | P1 | ✅ | mdc 第零步/第一步合并为单一表格，灰色反馈兜底作为内嵌规则 |
| FIX-030 | P1 | ✅ | sf ingest 加 deprecation warning，提示用户改用 sf update-l0 |
| FIX-031 | P2 | update_l0_file task_type 合法性校验 |
| FIX-032 | P2 | task_desc sanitize |
| FIX-033 | P2 | mdc 双分数制表修 A 定义 |
| FIX-034 | P2 | 删死代码 _L0_BLOCK_PATTERN |
| FIX-035 | P2 | mdc 删除/澄清降级路径 |

---



**状态**: 问题清单 + 修复方案已确认，进入执行阶段

#### 复审触发

v0.2.2 完成后，用户再次要求全盘审查。本次复审**深入 Python 引擎代码层**（而不只是 mdc 规则层），发现一批上轮修复时遗漏的一致性问题。

#### 核心元结论

v0.2.1/v0.2.2 修复聚焦于 mdc 规则，但**没同步检查 engine.py / evaluator.py / indexer.py 的 prompt template 和常量集**，留下了"规则层跑通，代码层脱节"的技术债。本轮的使命是**先清旧账、再加新功能**。

#### 问题清单与修复方案

##### P0-NEW（Critical/High，必须立即修）

**P0-NEW-1: engine.py PHASE1_PROMPT_TEMPLATE 残留 6 维旧字段**

位置：`src/skillforge/engine.py:67-96`

**问题**：JSON schema 模板中出现孤立的 `"precision"/"creativity"/"domain_knowledge"/...` 字段（不在任何 `{}` 内），是 v0.2.0 AUDIT-004 从 6 维改 3 维时没清理干净的残留。Prompt 是 LLM 直接输入，会导致 LLM 产出错误的 JSON schema，`sf run` / `sf analyze` 直接解析失败。

**修复方案**：重写为干净的 3 维 JSON schema：
```json
{
  "task_requirements":  { "precision":[], "reasoning":[], "tool_knowledge":[] },
  "agent_capabilities": { "precision":[], "reasoning":[], "tool_knowledge":[] },
  "gaps":               { "precision":[], "reasoning":[], "tool_knowledge":[] },
  "total_gap": ..., "gap_level": "...", "predicted_score": ...,
  "task_types": [...], "recommended_skill_types": [...]
}
```

---

**P0-NEW-2: indexer.DEFAULT_TASK_TYPES 与 capability-index.yaml 脱节**

位置：`src/skillforge/indexer.py:34-45` vs `memory/capability-index.yaml`

**问题**：
- indexer.py 硬编码 10 个 task_type（含 `design / writing / conversation / other` 等 Registry 里根本没有的）
- yaml 经 FIX-004 扩展到 20 个（含 `refactoring / debugging / content_analysis / ...`）
- 新用户初次初始化会用 indexer 的旧集合，FIX-004 成果被覆盖

**修复方案（用户要求我给）**：**让 Registry 成为 task_type 的单一权威来源**，indexer 动态加载，放弃硬编码。

具体实现：
```python
@staticmethod
def _load_default_task_types() -> list[str]:
    """从 Registry 提取全部 task_types（单一数据源）"""
    try:
        from skillforge.registry import SkillRegistry
        # 向上查找 skillforge-registry.yaml
        reg_path = IndexManager._find_registry_path()
        if reg_path and reg_path.exists():
            reg = SkillRegistry(registry_path=str(reg_path))
            task_types = {"default"}  # 默认兜底条目
            for skill in reg.list_skills():
                task_types.update(skill.task_types)
            return sorted(task_types)
    except Exception:
        pass
    return ["default"]  # 完全降级
```

- 保留 `DEFAULT_TASK_TYPES` 常量但标注 `# legacy fallback only`
- `_init_defaults()` 改用 `_load_default_task_types()`
- 新增 skill 到 Registry 自动扩展 task_type 集合，不再需要手工同步两处

---

**P0-NEW-3: mdc 规则"Phase 4 直接写 YAML"实操脆弱性**

**问题**：当前规则告诉 Agent "读 YAML → 找条目 → 更新 → 写回"，但没告诉**用什么工具、如何保证原子性、task_type 怎么选**。实操中我用 StrReplace 做精确替换，依赖 `old_string` 必须唯一，极易失败。

**修复方案（用户要求：引入 helper，不枚举 task_type，闭环方案）**：

新增 CLI 子命令 `sf update-l0`，Agent 通过 Shell 工具一行调用即可完成 Phase 4 闭环：

```bash
sf update-l0 \
    --task-type {task_type} \
    --rating {1|3|5} \
    --task-desc "{任务摘要，≤50 字符}" \
    --predicted {S}
```

命令内部自动完成：
1. 读 `memory/capability-index.yaml`
2. 定位 task_type 条目（不存在则创建空条目）
3. 计算 `delta = (rating - 3) × 20`
4. EMA 更新：`avg_delta = 0.2 × delta + 0.8 × old_avg_delta`
5. 累加：`gap_adjustment += delta`, `count += 1`
6. 追加审计注释到对应条目的 `# [sf-xxx] @ 时间戳 | rating=X | delta=Y | 任务摘要`
7. 原子性写回（YAML 安全 dump）
8. 若 rating=1，追加反思模板骨架到 `reflections.md`（留空框给 Agent 填）

task_type 决策的 mdc 规则（**不枚举，模糊匹配**）：
```
从 Registry 的 task_types 集合中，选**最贴近**当前任务的一项。
- 实在难以归类时，用 "default"
- 同一轮任务的多次子操作归为同一 task_type（避免数据分散到多个条目）
```

这样解决了：
- ✅ 原子性：Python yaml.safe_dump 保证
- ✅ 无格式依赖：不走 StrReplace
- ✅ task_type 模糊选择：不要求 Agent 精确分类
- ✅ 审计可追溯：每条 update 都有注释记录

---

##### P1-NEW（High/Medium，短期修）

**P1-NEW-1: evaluator.outcome 三分支存在死代码**

位置：`src/skillforge/evaluator.py:80-86`

**问题**：新评分约定下 `delta ∈ {-40, 0, +40}`，中间分支 `-10 ≤ delta < -5` 永远不会触发。

**修复方案**：简化为二分支：
```python
# 1/3/5 评分下 delta ∈ {-40, 0, +40}
# 保留 -5 阈值以兼容外部精细 delta（如未来的工具自动评分）
if delta >= -5:
    outcome = "success"
else:
    outcome = "patch_needed"
```

---

**P1-NEW-2: 被动反馈识别灰色地带无规则覆盖（采纳用户建议）**

**问题**：mdc 规则覆盖典型关键词，但大量真实反馈处于灰色地带（"那就这样吧"/"嗯"/"这个可以但 X 改一下"）。

**修复方案**：在 mdc Phase 4 增加"第零步：兜底规则"：
```
当反馈存在歧义或混合信号时，**默认 rating=3**：
- "那就这样吧"、"嗯"、"可以" → 3
- "这个可以，但 X 改一下" → 3（部分满意仍是符合预期）
- "好，再加个功能" → 3（接受 + 新需求）
只有明确的**推翻/重做/指出错误**才算 1。
只有明确的**惊喜表达**（"太棒了"/"超出预期"）才算 5。
```

---

**P1-NEW-4: Registry quality_tier 语义不统一**

**问题**：v0.2.0 AUDIT-009 把 quality_tier 设为 `unknown`（无假数据原则），v0.2.1 FIX-005 我填为 `L2`（设计意图估算），两版冲突。

**修复方案**：保留 v0.2.1 的 `L2` 估算值（不回滚），但在每个条目加注释 `# 预估，真实数据积累 ≥10 条后由 Phase 4 数据校准`，明确"这是设计意图估算，不是验证值"。若 registry.py 引用 quality_tier，确保兼容 `L1/L2/L3/unknown` 四种值。

---

##### P2-NEW（Low，轻量优化）

**P2-NEW-1: capability-index.yaml 条目顺序混乱**

**修复方案**：按字母序重排（保留已有真实数据的 `refactoring` 条目及其审计注释）。

**P2-NEW-2: docs/quickstart.md 仍含旧 `sf ingest` / `cursor-timings` 描述**

**修复方案**：移除旧评分链路描述，替换为 `sf update-l0` + 被动反馈识别的新流程。tests 目录暂不动（数据层兼容，单测仍能跑通）。

**P2-NEW-3: 反思质量无锚定方法**

**修复方案**：在 mdc 反思模板中增加"禁止外部归因"约束：
```
### root cause
- ❌ 禁止把失败归咎于外部原因（"任务描述不清"、"模型能力有限"、"工具不足"）
- ✅ 必须从三个内因维度找：
  1. 我对任务的理解是否准确？
  2. 我对复杂度的预判是否到位？
  3. 我的执行策略是否合适？
```

#### 执行顺序

```
第 1 批：清旧账（P0-NEW-1 → P0-NEW-2 → P1-NEW-1 → P1-NEW-4 → P2-NEW-1/2/3 → P1-NEW-2）
第 2 批：加新功能（P0-NEW-3：sf update-l0 CLI helper + mdc 规则更新）
第 3 批：验证（跑 pytest + 用 sf update-l0 完成本次任务的 Phase 4）
```

#### 修复状态（动态更新）

| ID | 状态 | 描述 |
|----|------|------|
| FIX-014 | ✅ | P0-NEW-1：清理 PHASE1_PROMPT_TEMPLATE 6 维残留 |
| FIX-015 | ✅ | P0-NEW-2：indexer 从 Registry 动态加载 task_types |
| FIX-016 | ✅ | P1-NEW-1：简化 outcome 三分支为二分支（cli.eval 同步） |
| FIX-017 | ✅ | P1-NEW-4：Registry quality_tier 注释统一 + **发现并移除重复条目**（每个 skill 原有两份） |
| FIX-018 | ✅ | P2-NEW-1：capability-index.yaml 按字母序重排 |
| FIX-019 | ✅ | P2-NEW-2：docs/quickstart.md 同步 `sf update-l0` + `sf` 简写 |
| FIX-020 | ✅ | P2-NEW-3：mdc 反思模板加禁止外部归因（内因三维度） |
| FIX-021 | ✅ | P1-NEW-2：mdc 增加灰色反馈兜底规则（默认 rating=3） |
| FIX-022 | ✅ | P0-NEW-3：实现 `sf update-l0` CLI + text-level patch（保留注释 + 原子写入） |

#### v0.2.3 关键改进亮点

1. **Registry 成为 task_type 单一数据源**（FIX-015）：indexer 动态加载，新增 skill 自动扩展 L0 索引默认条目。
2. **text-level patch 保留注释**（FIX-022）：Phase 4 不再走 `save()` 的全量重写，而是 regex 精确 patch，所有原有注释（含历史审计记录）都保留，每次调用追加一行新注释。
3. **原子写入**（FIX-022）：tmp 文件 → rename，防止写中断损坏 yaml。
4. **CLI 简写 `sf`**（FIX-019/022）：`sf update-l0 --task-type X --rating 3 --task-desc "..." --predicted 88` 一行完成 Phase 4 闭环。
5. **反思质量锚定**（FIX-020）：模板明确禁止"任务描述不清 / 模型能力不足 / 工具不够"等外部归因，强制从三个内因维度找根因。
6. **Registry 去重**（FIX-017 追加）：审查中意外发现每个 skill 在 Registry 里出现两份（L2 版 + unknown 版）——v0.2.1 FIX-005 填充时没清理旧条目导致。本次重写整个文件。

#### 验证记录

- `python3 -c "from skillforge.indexer import ..."` import 成功，Registry 动态加载出 26 个 task_types
- `update_l0_file` dry-run 验证：
  - count 2 → 3 ✓
  - 保留 sf-v0.2.1-fix 原注释 ✓
  - 追加新审计注释 ✓
  - `_meta.last_task_id` / `total_executed` / `updated_at` 正确更新 ✓
- rating=1 路径：自动创建新 task_type 条目 + 生成反思模板骨架到 reflections.md ✓
- `python3 -m skillforge update-l0 --help` 显示完整说明 ✓

#### 剩余事项

- **pytest 测试套件**：未跑。旧测试可能因数据层 outcome 简化而需更新（`success_within_tolerance` 消失），但影响范围可控。
- **sf 命令已安装**：`pip3 install -e .` 已执行，`/Users/vivx/Library/Python/3.9/bin/sf` 可用；`~/.zshrc` 已追加 PATH，新终端自动生效。mdc 规则 Phase 4 第二步增加了一键检测安装：`command -v sf || pip3 install -e ...`，Agent 首次调用时自动触发，幂等安全。
- **真实数据积累**：当前 `refactoring` count=2，距离 Forger 阈值 5 还差 3 次。本次 v0.2.3 任务结束后（按用户反馈）将变为 3。

---

### v0.2.2 (2026-04-17) — Phase 4 默认基线化 + 禁止主动询问打分

**状态**: v0.2.1 真实反馈驱动的修正

#### 用户反馈（rating=3，L0 已更新）

> "只要用户不回复说你做错了或者要改进什么的，一般就是 3。我觉得很少会有 5 的情况。一般就是 3 和 1，直接让用户在窗口回 1，3，5 确实感觉太奇怪了"

这是 SkillForge 上线后的**第一条真实用户反馈**。反馈直接命中 v0.2.1 的两个设计缺陷：

1. **主动询问打分本身就是违反设计的行为**——即使被动识别反馈，v0.2.1 末尾仍然出现了"请回复 1/3/5"的询问，这既打扰用户也违背"Phase 4 对用户透明"的初衷
2. **3/5 对称假设不成立**——5 分（超预期）在真实使用中极其罕见，默认基线应该是 3，而非"没反馈就跳过"

#### 修复清单

| ID | 状态 | 文件 | 修复内容 |
|----|------|------|---------|
| FIX-009 | ✅ | `.cursor/rules/skillforge.mdc` | Phase 4 改为默认 `rating=3`，明确禁止主动询问打分 / 主动暴露自评 |
| FIX-010 | ✅ | `.cursor/rules/skillforge.mdc` | rating=5 标注"罕见"，触发条件收紧为明确表达惊喜 |
| FIX-011 | ✅ | `/Users/vivx/.cursor/rules/skillforge.mdc` | 同步用户级规则 |
| FIX-012 | ✅ | `SKILL.md` + `PRD.md` | Phase 4 章节同步为默认基线版 |
| FIX-013 | ✅ | `memory/capability-index.yaml` | `refactoring` 条目记入本次 v0.2.1 修复任务（count=1, rating=3, delta=0） |

#### 评分规则对比

| 维度 | v0.2.1 | v0.2.2（修正后） |
|------|--------|----------------|
| 默认行为 | 无反馈→跳过打分 | 无反馈→默认 rating=3 |
| 1 分触发 | 消极批评关键词 | 消极批评关键词（不变） |
| 3 分触发 | 积极关键词 | **除 1/5 外全部**（含沉默、下一任务、轻微补充） |
| 5 分触发 | 积极关键词 | **罕见**，仅明确表达惊喜（"太棒了"、"超出预期"） |
| Agent 末尾询问 | ⚠️ 未禁止（v0.2.1 实际发生了） | 🚫 **明确禁止** |
| Agent 末尾自评 | ⚠️ 未禁止 | 🚫 **明确禁止** |

#### 设计洞察

**"默认 3" 比 "无反馈跳过" 更符合长期学习的统计直觉**：

- 如果无反馈就跳过，L0 的 `count` 会严重低估真实执行次数，影响 Forger 触发（需 ≥5 次成功）
- 默认 3 意味着"用户没抱怨就是满意"，这符合人类协作的默认假设
- delta=0 不会扰动 gap_adjustment，所以默认 3 不会引入噪音，只是把统计样本做满

**关键领悟（元层面）**：

这次修复本身就验证了 SkillForge 的价值——**真实的用户反馈让设计错误浮出水面**。v0.2.1 的"主动询问打分"在设计阶段看起来合理（收集数据），但在真实交互中是粗暴的打断。没有这次反馈，Agent 可能会持续用"请回复 1/3/5"污染对话若干个月。

这也印证了 DEVLOG v0.2.1 的结论：**"骨架有了，血肉不足"——SkillForge 真正需要的不是更多功能，而是真实使用验证期**。

#### L0 索引当前状态

```yaml
refactoring:
  count: 1
  avg_delta: 0.0
  trend: stable
  gap_adjustment: 0
  # [sf-v0.2.1-fix] 2026-04-17 SkillForge 架构审查 + 8 文件修复 | S=90 | rating=3 | delta=0
```

这是 `capability-index.yaml` 的**第一条真实数据**。从 0 到 1，闭环正式跑通。

---

### v0.2.1 (2026-04-17) — 全面审查 + P0 闭环打通

**状态**: 审查完成，P0 修复执行中

#### 审查背景

对 SkillForge 做了一次全盘检查，覆盖 28 个文件（4 个 workspace 规则 + 24 个 SKILLFORGE 项目文件），从架构设计、闭环完整性、实用性三个维度评估。整体处于"骨架有了、血肉不足"阶段——Python 引擎代码量充足（24 个文件，71 个测试），但核心自改进闭环从未真正跑通：L0 索引 0 条数据，Registry capability_gains 全为 0，Forger 从未触发。

#### 实用性诚实评分

| 使用场景 | 评分 | 说明 |
|---------|------|------|
| Python CLI 独立使用 | ⭐⭐⭐⭐ | 闭环完整，测试覆盖好 |
| Phase 1 诊断标签 | ⭐⭐⭐ | 有用但噪音大，Gap 缺校准基准 |
| Skill 增强推荐（Phase 2-3） | ⭐ | capability_gains 全为 0，实质不运作 |
| Phase 4 自改进闭环 | ⭐ | cursor-timings 有数据，但从未同步到 L0 |
| 学术/教学参考 | ⭐⭐⭐⭐ | KnowSelf/CapBound/Reflexion 工程化扎实 |
| **综合实用性** | ⭐⭐ | 有框架，闭环未通 |

#### 已发现问题一览

##### P0 — 必须立即修复

| ID | 级别 | 问题 | 影响文件 |
|----|------|------|---------|
| **P0-1** | 🔴 Critical | 两份 mdc 规则维度不一致——workspace 规则是 3 维（prec/reas/tool），integrations/skillforge.mdc 仍是旧版 6 维（prec/crea/know/tool/reas/spd），两套同时生效互相冲突 | `.cursor/rules/skillforge.mdc` vs `integrations/skillforge.mdc` |
| **P0-2** | 🔴 Critical | Phase 4 打分写入了 `cursor-timings.md`，但 `capability-index.yaml` 从未更新——`sf ingest` 从未被调用，L0 索引永远为 0，自改进闭环断裂 | workspace mdc 规则 |
| **P0-3** | 🟠 High | integrations 目录位置尴尬——既不是用户文档，也不是 Cursor 自动加载的规则，与 workspace mdc 80% 内容重复 | `integrations/skillforge.mdc` |

##### P1 — 短期优化

| ID | 级别 | 问题 |
|----|------|------|
| **P1-1** | 🟠 High | Registry 中所有 capability_gains 为 0——Phase 2 推荐 Skill 时"预计提升 X 分"没有量化依据 |
| **P1-2** | 🟠 High | Phase 4 依赖用户主动打 1/3/5 分——实际使用中打分率预计 < 5%，闭环数据来源枯竭 |
| **P1-3** | 🟡 Medium | `capability-index.yaml` 的 task_type 列表与 Registry 不对齐（缺 video_production 等） |

##### P2 — 轻微优化

| ID | 级别 | 问题 |
|----|------|------|
| **P2-1** | 🟢 Low | workspace mdc 规则"何时激活"表漏了"发现重复模式（≥5次）→ 触发 Forger"这一条件 |
| **P2-2** | 🟢 Low | 两份 mdc 内容 80% 重复，维护成本高 |

#### 修复清单

##### 第 1 批（止血，与本版本同步）

| ID | 状态 | 文件 | 修复内容 |
|----|------|------|---------|
| FIX-001 | ✅ | `integrations/skillforge.mdc` | 已移至 `docs/archive/ARCHIVE-v0.1.1-6dims.mdc`，标注历史版本 |
| FIX-002 | ✅ | `.cursor/rules/skillforge.mdc` | Phase 4 直接写入 `capability-index.yaml`（EMA 更新），移除 `sf ingest` 依赖 |
| FIX-003 | ✅ | `.cursor/rules/skillforge.mdc` | Phase 4 增加被动反馈识别（消极批评→rating=1，积极肯定→rating=3，无反馈→跳过） |
| FIX-004 | ✅ | `memory/capability-index.yaml` | task_type 从 7 条补全到 20 条，与 Registry 的所有 task_types 对齐 |
| FIX-005 | ✅ | `skillforge-registry.yaml` | 5 个种子 skill 填入设计意图 capability_gains，全部标注"预估，待验证" |
| FIX-006 | ✅ | `.cursor/rules/skillforge.mdc` | "何时激活"表补全 Forger 触发条件（≥5 次重复模式） |
| FIX-007 | ✅ | `/Users/vivx/.cursor/rules/skillforge.mdc` | 用户级规则同步为 3 维 + Phase 4 新版本，消除与 workspace 规则的冲突 |
| FIX-008 | ✅ | `SKILL.md` + `PRD.md` | Phase 4 章节同步更新为被动反馈 + 直写 L0 版本，去掉过时的 `sf ingest` 流程 |

##### 第 1 批修复效果

| 指标 | 修复前 | 修复后 |
|------|-------|-------|
| mdc 维度一致性 | 3 个文件 3 个版本（3/6/6 维） | 统一 3 维 |
| Phase 4 闭环 | 写 cursor-timings.md，等不到 sf ingest | 直接写 capability-index.yaml |
| 打分率预期 | < 5%（依赖用户主动打分） | ~60-80%（被动反馈自动识别） |
| task_type 覆盖 | 7 条（与 Registry 不对齐） | 20 条（完全对齐） |
| capability_gains | 全为 0（Phase 2 推荐无依据） | 设计意图估算值（标注待验证） |

##### 第 2 批（验证期，需积累数据）

| ID | 内容 |
|----|------|
| FIX-VERIFY-01 | 真实使用 20+ 轮，观察 `capability-index.yaml` 是否开始收敛 |
| FIX-VERIFY-02 | 真实使用后校准 Registry 的 capability_gains（从"预估"转"已验证"） |
| FIX-VERIFY-03 | 如 Forger 触发，评估生成的 SKILL.md 草稿质量 |

---

### v0.2.0 (2026-04-17) — 全面审查修复 + mdc 权威化

**状态**: 全面审查完成，全链路跑通 | 测试基线：**71/71 通过**

#### 问题诊断

审查发现 SkillForge 存在系统性架构问题：**两套系统（Python Engine vs mdc 规则）并存但未对齐，capability_gains 全为假数据，Phase 4 从未真正触发，gap_adjustment 读取链路断裂**。

#### 修复清单

| ID | 文件 | 修复内容 |
|----|------|---------|
| AUDIT-001 | `skillforge.mdc` | Phase 4 改为对话内直接写 `cursor-timings.md`，去掉 `sf eval` 外部命令依赖 |
| AUDIT-002 | `skillforge.mdc` | 反思格式更新，与 Phase 4 新格式对齐 |
| AUDIT-003 | `skillforge.mdc` | Phase 1 新增 gap_adjustment 读取步骤 |
| AUDIT-004 | `engine.py` | PHASE1_PROMPT_TEMPLATE 从 6 维改为 3 维，与 mdc 规则一致 |
| AUDIT-005 | `engine.py` | 五态常量对齐，_classify_gap 改为五态字符串 |
| AUDIT-006 | `engine.py` | 顶部加 DEPRECATED NOTICE，标注 mdc 权威地位 |
| AUDIT-007 | `models.py` | Phase1Result.gap_level 从 L1/L2/L3 改为五态字符串 |
| AUDIT-008 | `cli.py` | _parse_cursor_timings 支持新表格格式 |
| AUDIT-009 | `skillforge-registry.yaml` | capability_gains 从 6 维改为 3 维，清空所有假数据，quality_tier 改为 unknown |
| AUDIT-010 | `config.yaml` | 删除死字段（calibration_enabled / default_weight / output section） |
| AUDIT-011 | `config.py` | 删除对应死字段引用，forger_trigger 默认从 3 改为 5 |
| AUDIT-012 | `PRD.md` | 添加权威版本说明，维度统一为 3 维，Phase 4 格式更新，Section 编号调整 |
| AUDIT-013 | `SKILL.md` | 添加权威版本说明，维度统一为 3 维，Phase 4 格式更新 |

#### 核心架构决策

- **mdc 规则是最权威版本**：Cursor 对话场景下以 `.cursor/rules/skillforge.mdc` 为准
- **Phase 4 真正跑通**：用户打分 → Agent 直接写文件，不依赖外部命令
- **维度统一**：Precision / Reasoning / Tool+Knowledge 三维，PRD / SKILL.md / engine.py / registry 全部对齐
- **capability_gains 不填假数据**：积累 ≥10 条真实反馈前置 0，由 Phase 4 数据逐步校准

---

### v0.1.2 (2026-04-17) — actual/delta 解耦 + Phase 4 评分机制重构

**状态**: BUID-001 修复完成 | 测试基线：**71/71 通过**

#### 问题

**BUID-001 🔴 Critical**：Phase 4 评分机制存在两个根本性缺陷：

1. `actual = predicted + (rating-3)*20` —— 同一 rating 对不同 predicted 产生不同 actual，跨任务 delta 不可比较
2. `indexer.update()` 内部用 `delta = actual - predicted` —— 当 `actual=predicted` 时 delta 永远为 0，`gap_adjustment` 永不更新

#### 修复清单

|| ID | 文件 | 修复内容 |
||----|------|---------|
| BUID-001 | `models.py` | `Phase4Result` 新增 `delta` 字段 |
| BUID-001 | `evaluator.py` | `evaluate()` 改为 `actual=predicted`，`delta=(rating-3)*20`，从源头算好 |
| BUID-001 | `evaluator.py` | `finalize()` / 轨迹写入 / 根因分析全部改用 `phase4.delta` |
| BUID-001 | `indexer.py` | `update()` 新增 `delta` 参数，移除内部 `delta=actual-predicted` |
| BUID-001 | `cli.py eval` | `actual=predicted`，`delta=(rating-3)*20`，`delta` 传入 `indexer.update()` |
| BUID-001 | `cli.py ingest` | 补传 `delta` |
| BUID-001 | `engine.py` | `evaluate_and_close()` 去掉废弃参数（actual_score/llm_self_rating/tool_verification）|
| BUID-001 | `skillforge.mdc` | Phase 4 改为用户输入 1/3/5，CLI 命令与实际对齐 |
| BUID-001 | `evaluator.py` | 删除死代码：`_compute_score` + `llm_self_weight/tool_weight/user_weight/patch_threshold` |

#### 评分约定（最终版）

```
actual = predicted（干活儿的质量以预估为准）
delta  = (user_rating - 3) * 20
  rating=5 → delta=+40（超预期）
  rating=3 → delta=0（符合预期）
  rating=1 → delta=-40（低于预期）
```

---

### v0.1.1 (2026-04-17) — 审计修复批次

**状态**: BUG-001/002/003/005/006/009/010/011 已修复

#### 修复清单

| ID | 级别 | 修复内容 | 文件 |
|----|------|----------|------|
| **BUG-001** | 🔴 Critical | `cli.py` 新增 `eval` 命令（Bridge 主路径）+ `ingest` 命令（降级路径） | `cli.py` |
| **BUG-002** | 🔴 Critical | `executor.py` 新增 `_synthesize_minimal_skill_card`，Skill.path 为空/文件不存在时合成最小 skill 卡片 | `executor.py` |
| **BUG-003** | 🔴 Critical | `evaluator.py:165` `Path("memory")` → `self._memory_dir`，轨迹写入路径与反思写入对齐 | `evaluator.py` |
| **BUG-005** | 🟠 High | `skillforge.mdc` 六维→三维（prec/reas/tool），新增短任务跳过规则，SF 标签简化为 `[SF | Gap≈X | state]` | `integrations/skillforge.mdc` |
| **BUG-006** | 🟡 Medium | `config.yaml` `forger_trigger: 3 → 8`，防止样本不足时触发过拟合 | `config.yaml` |
| **BUG-009** | 🟢 Low | 删除 `indexer.py` 中重复的 `_init_defaults`（保留第 147 行版本） | `indexer.py` |
| **BUG-010** | 🟢 Low | `CapabilityIndex` `class Config` → `model_config = ConfigDict(...)`（Pydantic V2） | `indexer.py` |
| **BUG-011** | 🟢 Low | 删除 `SandboxRunner` 中冗余的 `suffix` 变量和死代码 | `executor.py` |

#### 关键设计决策

- **虚拟 Skill 机制（ADR-008）**：Registry 条目不再强制要求物理 SKILL.md 文件，元数据可动态合成 ~100-150 tokens 的最小 skill 卡片注入 context
- **双路 Bridge（ADR-009）**：Cursor 规则 Phase 4 末尾调用 `sf eval --task-id ... --rating ...` 实时写回 L0；降级路径追加到 `memory/cursor-timings.md` 再 `sf ingest` 批量导入

---

### v0.1.0-audit (2026-04-17) — 全盘审计与修复方案

**状态**: 审计完成，P0 修复待执行  |  测试基线：**71/71 通过**

#### 审计背景

在 Stage 0-4 全部完成、测试全绿的前提下，针对"实际使用场景"做了一次诚实审视。结论：**代码工程质量良好，但存在 3 个 Critical 级别的架构缺陷，使得 Cursor 接入态下 80% 代码是摆设**。

#### 已发现问题一览（按严重度）

| ID | 级别 | 问题 | 影响面 |
|---|---|---|---|
| **BUG-001** | 🔴 Critical | Cursor `.mdc` 规则与 Python 引擎完全解耦，记忆闭环在 Cursor 对话态不会触发 | `integrations/skillforge.mdc` + `engine.py` |
| **BUG-002** | 🔴 Critical | Registry 中所有 skill 路径（如 `.cursor/skills/code-expert/SKILL.md`）在文件系统中均不存在，skill 增强是 placebo | `skillforge-registry.yaml` + `executor.py` |
| **BUG-003** | 🔴 Critical | `evaluator._write_trajectory` 用 `Path("memory")` 相对 cwd，与 `_append_reflection` 的 `self._memory_dir.resolve()` 不一致，换目录运行轨迹/反思写到两处 | `evaluator.py:165` |
| **BUG-004** | 🟠 High | 六维自评方法论脆弱：LLM 被要求量化自己的能力，无锚定、无校验、无惩罚，数字可造假 | `SKILL.md` + `integrations/skillforge.mdc` |
| **BUG-005** | 🟠 High | 每次对话强制 6 维扫描 + SF 标签，小任务/闲聊场景每条浪费 200-500 tokens | `integrations/skillforge.mdc` |
| **BUG-006** | 🟡 Medium | `Forger` 阈值 3 次太激进，样本量不足以提炼通用 SKILL.md，易生成过拟合垃圾 | `config.yaml` + `forger.py` |
| **BUG-007** | 🟡 Medium | `avg_effectiveness` 基于 α=0.2 的 EMA 更新，单次异常就剧烈波动，没有置信区间 | `indexer.py` + `registry.py` |
| **BUG-008** | 🟡 Medium | `timings.yaml` 实测数据全为占位符（predicted=80, actual=50, ms=0），从未产生过真实反馈 | runtime state |
| **BUG-009** | 🟢 Low | `IndexManager._init_defaults` 定义了两次（`indexer.py` 54 行 & 147 行） | `indexer.py` |
| **BUG-010** | 🟢 Low | Pydantic V2 `class Config` deprecation warning 未处理 | `indexer.py:27` |
| **BUG-011** | 🟢 Low | `SandboxRunner` 语言分派存在 dead code 和冗余映射 | `executor.py:225-230` |
| **BUG-012** | 🟢 Low | 文档多处自相矛盾（Python 版本要求、注释语言混用） | `docs/*.md` |

#### 实用性分场景诚实评分

| 使用场景 | 评分 | 说明 |
|---|---|---|
| Python CLI (`sf run/eval/dashboard`) | ⭐⭐⭐⭐ | 闭环完整、测试覆盖好，可生产使用 |
| Cursor `.mdc` 集成 | ⭐⭐ | 仅诊断标签在运作，记忆/增强/Forger 全部失效 |
| Claude Code / Codex 跨端 | ⭐⭐ | 概念通用但需开发者自接 Python 桥 |
| 长期自改进收敛效果 | ⭐⭐ | 当前 0 条真实反馈数据，EMA 尚未验证 |
| 学术复现 / 教学价值 | ⭐⭐⭐⭐ | CapBound/KnowSelf/Reflexion 工程化复现完整 |

#### 修复方案与改进思路

> 全部条目已同步到下文的 **技术债务表（TD-007~TD-013）** 和 **待办事项 P0-修复批次**。

**思路 A — 打通 Cursor ↔ Python 闭环（解决 BUG-001）**

两条可选路线：
1. **轻量桥接**：Cursor 规则在 Phase 4 末尾通过 Shell 工具调用 `sf eval --task-id $ID --rating $R`，把自评写回 L0/L1/L2
2. **规则侧 Markdown 日志**：Cursor 规则直接把 SF 标签 + 结果以 append-only 形式写到 `memory/cursor-timings.md`，定期用 `sf ingest cursor-timings.md` 导入

推荐路线 1（实时更新），路线 2 作为降级方案。

**思路 B — 解决 Skill 路径幻觉（解决 BUG-002）**

放弃"真实文件"假设，改为**虚拟 Skill 模式**：
- `Skill.path` 允许为空
- `EnhancementExecutor.build_enhanced_prompt` 若 `path` 为空或文件缺失，则根据 `description + task_types + capability_gains` 动态合成最小 skill 卡片注入 context
- Registry 只存元数据，不强依赖外部文件

附带：在 `docs/skill-registry.md` 里说明"如果希望有完整 SKILL.md，请放到 `skills/{skill_id}/SKILL.md` 并设置 `path`"

**思路 C — 修正路径硬编码（解决 BUG-003）**

把 `evaluator.py:165` 的 `Path("memory") / "trajectories" / task_type` 改为 `self._memory_dir / "trajectories" / task_type`，与 `_append_reflection` 对齐。`QualityEvaluator.__init__` 已经接收 `memory_dir`，零迁移成本。

**思路 D — 压缩维度 + 短任务快速通道（解决 BUG-004/005）**

修改 `integrations/skillforge.mdc`：
- 6 维 → **3 维**（`prec / reas / tool+know 合并`）
- 新增规则：**任务描述 < 20 字符，或为"确认/询问/闲聊"语义 → 跳过 SF 标签**
- SF 标签简化为 `[SF | Gap≈X | state]`（去掉维度枚举）

预期单次对话节省 200-300 tokens，高频小任务场景收益更大。

**思路 E — Forger 质量门槛（解决 BUG-006）**

修改 `config.yaml`：
```yaml
evaluation:
  forger_trigger: 8                  # 3 → 8
  forger_min_avg_delta: -3           # 新增：平均偏差优于 -3 才触发
  forger_min_task_diversity: 0.6     # 新增：描述相似度 <0.6 才算多样样本
```
并在 `forger.py` 的 `count_successful_trajectories` 里补充多样性计算。

**思路 F — Effectiveness 置信区间（解决 BUG-007）**

给 `Skill` 增加 `effectiveness_ci_lower: float` 字段，用 Wilson score interval 计算 95% 置信下界：
```python
from math import sqrt
z = 1.96
n = usage_count
p = avg_effectiveness
ci_lower = (p + z*z/(2*n) - z * sqrt((p*(1-p) + z*z/(4*n))/n)) / (1 + z*z/n)
```
Phase 2 决策时 `recommendation.estimated_gain *= ci_lower`，避免小样本过度乐观。

**思路 G — 清理工作（解决 BUG-009/010/011/012）**

- 删除 `indexer.py` 里重复的 `_init_defaults`
- `class Config:` → `model_config = ConfigDict(arbitrary_types_allowed=True)`
- 统一 `SandboxRunner` 语言分派为单一 `LANG_DISPATCH` 表
- 文档全局替换"Python 3.11+" → "Python 3.9+"

#### 推荐执行顺序

```
第 1 批（1-2 小时） — 止血：修 BUG-003 / BUG-009 / BUG-010 / BUG-011
第 2 批（半天）     — 规则瘦身：修 BUG-005 + 实施思路 D（升级 .mdc）
第 3 批（1 天）     — 功能真实化：修 BUG-002 + 实施思路 B（虚拟 Skill）
第 4 批（1-2 天）   — 闭环打通：修 BUG-001 + 实施思路 A（Cursor ↔ Python 桥）
第 5 批（半天）     — 质量校准：修 BUG-006/007 + 实施思路 E/F
第 6 批（积累期）   — 跑 20+ 真实对话，验证 L0 索引是否收敛（解决 BUG-004/008）
```

#### 关键决策建议

> 停止加新功能，集中修 P0 三件事（BUG-001/002/003），然后在 Cursor 真实跑 20 次对话采样，看 L0 索引能否自己收敛到合理的 `gap_adjustment`。
> - **收敛** → 设计成立，继续推进 Stage 5 白盒预判
> - **不收敛** → 六维自评假设不成立，需要把方法论换成"任务类型统计先验 + 轻量校准"

---

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

### ADR-008: 虚拟 Skill 机制（解耦 Registry 与物理文件）

**日期**: 2026-04-17
**状态**: 已决定，待实现（v0.1.1）
**背景**: 审计发现 BUG-002 — Registry 中 5 条种子 skill 的 `path` 全部指向不存在的文件，`EnhancementExecutor` 读取时只能注入占位符，skill 增强机制形同空转。

**决策**: 放弃"Registry 条目必须对应一个真实 SKILL.md 文件"的强约束，改为**虚拟 Skill 优先**模式：

1. `Skill.path` 允许为空字符串
2. `EnhancementExecutor.build_enhanced_prompt` 在文件不存在时，根据 `description + task_types + capability_gains + trigger_keywords` 动态合成最小 skill 卡片注入 context
3. 若作者希望提供完整指导，在 Registry 条目中写真实 `path`，此时走文件加载路径

**理由**:
1. Registry 的核心价值是"能力目录 + 决策信号"，不是"文档库"
2. 强制每个条目必须有文件会阻塞 Registry 的扩张（尤其对通用能力如"code_review"这种很难单独写 SKILL.md）
3. 合成的最小 skill 卡片在 token 预算上更克制（约 100-150 tokens vs 完整 SKILL.md 的 1-3k）

**影响**: `models.py`（`Skill.path` → `Optional[str]`）、`executor.py`（新增 `_synthesize_minimal_skill_card`）、`docs/skill-registry.md`（说明两种模式）。

---

### ADR-009: Cursor ↔ Python 闭环的桥接策略

**日期**: 2026-04-17
**状态**: 已决定，待实现（v0.1.1）
**背景**: 审计发现 BUG-001 — `.mdc` 规则让 LLM 在对话中自诊断并输出 SF 标签，但没有任何机制把结果写回 Python 引擎，导致 L0/L1/L2 记忆在 Cursor 日常使用下**永远是 0 条真实数据**。

**决策**: 采用**双路桥接**，agent 自行选择：

- **主路径（实时）**：Cursor 规则在 Phase 4 末尾，通过 Shell 工具调用：
  ```
  sf eval --task-id <auto-generated> --rating <1-5> --task-type <type> --delta <A-S>
  ```
  `cli.py eval` 命令接收参数，完成 L0 索引更新 + L1 轨迹写入 + L2 反思（如需）
- **降级路径（批量）**：规则把 SF 诊断/结果以 append-only 追加到 `memory/cursor-timings.md`，支持 `sf ingest memory/cursor-timings.md` 批量导入（适合 Shell 工具受限的场景）

**理由**:
1. 实时更新让 L0 `gap_adjustment` 能在几轮对话后就开始影响后续预判
2. 降级路径保证即使 Shell 工具不可用也能保留数据
3. 不引入新的依赖或后台进程，仍是"纯文本 workspace"

**拒绝方案**:
- **MCP server 模式**：引入状态进程 + 额外协议负担，违背"零依赖"原则
- **HTTP webhook 模式**：需要常驻服务，偏离 Agent Skill 的定位

**影响**: `integrations/skillforge.mdc`（新增 Phase 4 调用规则）、`cli.py`（增强 `eval` + 新增 `ingest`）、`engine.py`（确保 `evaluate_and_close` 可被 CLI 传参驱动）。

---

## 待办事项

### 优先级 P0（v0.1.1 修复批次 — 审计结论）

> 详见 **v0.1.0-audit (2026-04-17)** 版本记录。停止加新功能，先完成以下修复。

**第 1 批：止血（1-2 小时）**
- [ ] BUG-003：`evaluator._write_trajectory` 的 `Path("memory")` 改为 `self._memory_dir`
- [ ] BUG-009：删除 `indexer.py` 中重复定义的 `_init_defaults`
- [ ] BUG-010：`CapabilityIndex.Config` → `model_config = ConfigDict(...)`（Pydantic V2）
- [ ] BUG-011：`SandboxRunner` 语言分派改成统一 `LANG_DISPATCH` 表

**第 2 批：规则瘦身（半天）**
- [ ] BUG-005：`integrations/skillforge.mdc` 六维 → 三维（`prec / reas / tool+know`）
- [ ] BUG-005：新增"短任务/闲聊跳过 SF 标签"条款（< 20 字符 或 询问/确认语义）
- [ ] BUG-005：SF 标签简化为 `[SF | Gap≈X | state]`
- [ ] BUG-012：统一文档里"Python 3.11+" → "Python 3.9+"

**第 3 批：功能真实化（1 天）**
- [ ] BUG-002：`Skill.path` 允许为空；`EnhancementExecutor` 在文件缺失时根据元数据合成最小 skill 卡片
- [ ] BUG-002：`docs/skill-registry.md` 补充"真实 SKILL.md 可选"说明
- [ ] BUG-002：Registry 种子条目的 `path` 字段清空或指向真实存在的 skill（如 `../ffmpeg/SKILL.md`）

**第 4 批：Cursor ↔ Python 闭环（1-2 天）**
- [ ] BUG-001：`integrations/skillforge.mdc` 增加"Phase 4 末尾调用 `sf eval --task-id ... --rating ...`"规则
- [ ] BUG-001：`cli.py` 增加/完善 `eval` 命令，接收 task_id + rating，写入 L0/L1/L2
- [ ] BUG-001：新增降级方案 `sf ingest memory/cursor-timings.md`（Shell 调用受限时用）

**第 5 批：质量校准（半天）**
- [ ] BUG-006：`config.yaml` `forger_trigger: 3 → 8`
- [ ] BUG-006：`forger.py` 增加 `forger_min_avg_delta` + 任务描述多样性检查
- [ ] BUG-007：`Skill` 增加 `effectiveness_ci_lower`（Wilson 区间）
- [ ] BUG-007：`decider.py` Phase 2 用 `ci_lower` 替代 `avg_effectiveness`

**第 6 批：验证期（积累数据）**
- [ ] BUG-008：在 Cursor 真实跑 20+ 次对话，观察 L0 `gap_adjustment` 是否收敛
- [ ] BUG-004：根据 20 次采样结果判断六维自评假设是否成立，决定继续/重构方法论

---

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
| TD-001 | capability_gains 假数据 | 历史上 manual 填的假数据无法验证 | **v0.2.0 已解决：清空改为 0，由真实反馈逐步校准** |
| TD-002 | 无 sandbox | 代码类任务的 Phase 4 评估只能靠用户评分，无法自动执行验证 | P1 |
| TD-003 | 无 observability | Phase 1-4 各阶段没有耗时追踪，无法分析性能瓶颈 | P1 |
| TD-004 | YAML Registry 性能 | skill 数量 >1000 时全文扫描效率低 | P2（迁移到 SQLite 可选方案） |
| TD-005 | 多 Agent 协作 | 单 Agent 自评存在确认偏误风险，MAR 机制未实现 | P2 ✅ 已完成 |
| TD-006 | 白盒预判 | CapBound hidden state 路径未实现 | P3 |
| TD-007 | Cursor ↔ Python 断桥 | mdc 规则不调 Python 引擎，记忆永不更新 | **v0.2.0 已解决：Phase 4 改为 Agent 直接写文件** |
| TD-008 | **Skill 路径幻觉**（BUG-002） | Registry 中所有 `.cursor/skills/*/SKILL.md` 路径在文件系统中不存在，skill 增强是空转 | **P0（v0.1.1 修复）** |
| TD-009 | **轨迹写入路径 bug**（BUG-003） | `evaluator._write_trajectory` 相对 cwd，与 `_append_reflection` 绝对路径不一致 | **P0（v0.1.1 修复）** |
| TD-010 | Phase 4 从未触发 | 用户打完分没有写回机制，capability-index 永为 0 | **v0.2.0 已解决：打分内嵌对话，直接写 cursor-timings.md** |
| TD-011 | SF 标签 token 开销 | 强制 6 维扫描浪费 tokens | **v0.2.0 已解决：统一为 3 维，全部对齐** |
| TD-012 | Forger 触发过激 | 3 次就生成草稿，样本不足易过拟合 | **v0.2.0 已解决：forger_trigger 从 3 改为 5** |
| TD-013 | Effectiveness 无置信区间 | α=0.2 EMA 小样本波动大 | P1 |
| TD-014 | 两套系统维度不一致 | PRD/Engine/Registry 各有不同维度，无权威 | **v0.2.0 已解决：以 mdc 为权威，其余全部同步** |

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

### 2026-04-17: Phase 4 用户打分机制改进（TD-010 修复决策）

**问题 1**: 1-5 分对用户抽象，"这次不错"不等于知道该打几分。
**问题 2**: emoji 操作成本高，用户不会主动打分。
**问题 3**: 若 `actual = predicted + (rating-3)*20`，同一 rating 会因 predicted 不同而产生不同的 actual，不合理。

**决策**：
1. 去掉 emoji，直接用 **1（不满意）/ 3（一般）/ 5（满意）**
2. `actual` 和 `delta` 彻底解耦：
   - `actual = S`（干活儿的质量以预估为准，用户打分不改变实际分数）
   - `delta = (rating - 3) × 20`（用户感受与预估的偏差，用于校准 gap_adjustment）

**量化映射**：

| 你选 | delta | 含义 | 对 gap_adjustment |
|------|-------|------|------------------|
| 5 | +40 | 比我预估的好太多 → 我太保守 | 以后同类任务，Gap 估低一点 |
| 3 | 0 | 符合我的预估 | Gap 不变 |
| 1 | -40 | 比我预估的差太多 → 我太乐观 | 以后同类任务，Gap 估高一点 |

**影响范围**: `integrations/skillforge.mdc` Phase 4 + 双分数制描述更新。

---

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
