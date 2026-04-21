# Cursor 集成指南

> 五分钟让 Cursor Agent 具备 SkillForge 能力

---

## 接入步骤

### 1. 复制规则文件

将 `integrations/skillforge.mdc` 复制到你的项目 `.cursor/rules/` 目录：

```bash
cp integrations/skillforge.mdc your-project/.cursor/rules/skillforge.mdc
```

或者复制到全局规则目录（所有 Cursor 窗口生效）：

```bash
cp integrations/skillforge.mdc ~/.cursor/rules/skillforge.mdc
```

### 2. 安装 sf CLI（Phase 4 依赖）

```bash
cd /path/to/skillforge
pip install -e .
```

mdc 首次加载时会自动检测 `sf` 是否已安装；若缺失会提示一条一次性安装命令。

### 3. 重启 Cursor Agent

关闭当前对话窗口，开启新对话，规则自动加载。

---

## 验证是否生效

发送一个任务给 Cursor Agent，回复开头应该出现 SF 标签：

```
[SF | Gap≈3 | independent]
```

如果没有出现，检查：
1. `.cursor/rules/` 目录是否存在该文件
2. 文件开头是否包含 frontmatter（`---` 包裹的配置）
3. 是否是**新开的对话**（旧对话不会重新加载规则）

---

## SF 标签解读

```
[SF | Gap≈35 | force-enhance]
 │    │        │
 │    │        └── 五态状态
 │    └── 总 Gap（三维中的最大缺口）
 └── SkillForge 标识
```

v0.2.0 起标签格式**简化**为仅显示总 Gap + 状态。v0.1.x 曾列出非零维度（如 `tool+30,know+20`），但真正影响行为的是总 Gap 所落在的区间，维度细节对用户价值低。

### 三维度对照

| 简写 | 全称 | 含义 |
|------|------|------|
| `prec` | Precision | 幻觉风险高、数据必须准确、版本/API 细节易错 |
| `reas` | Reasoning | 多步骤依赖、复杂逻辑链、数学推导 |
| `tool` | Tool+Knowledge | 需要调用真实工具、专业壁垒高、细分领域知识稀缺 |

**Gap = max(prec, reas, tool)**（取最大维度为总 Gap，不做加权叠加）

### 五态状态含义

| 状态 | Gap 范围 | Agent 行为 |
|------|----------|-----------|
| `independent` | < 5 | 直接执行，不打断 |
| `light-hint` | 5~15 | 执行，结束时提示优化空间 |
| `suggest` | 15~30 | 询问是否启用 skill 增强 |
| `force-enhance` | 30~50 | 暂停，要求你确认方案 |
| `out-of-scope` | ≥ 50 | 坦白能力边界，不执行 |

---

## 常见场景

### 设计类任务（Gap 通常较低）

```
你: 帮我设计多租户 RBAC+ABAC 权限系统
Agent: [SF | Gap≈12 | light-hint]
...（直接给出设计方案，结尾轻提示"有优化空间"）
```

这是正常的——架构设计类任务 LLM 有大量训练数据，Gap 确实低。

### 实现类任务（Gap 通常较高）

```
你: 在我们的 Go 代码库里实现这套权限系统，对接 PostgreSQL row-level security
Agent: [SF | Gap≈40 | force-enhance]
Agent: 当前能力可能不足以达到最优结果。本地 Registry 为空（涌现式生长，
       尚无匹配 skill），建议：
       1. 拆解为：先让我梳理 RLS 策略 → 再写迁移脚本 → 再对接业务层
       2. 直接执行（高风险）
```

### 超出能力边界

```
你: 实时分析我们生产环境的 Pod 资源使用，并自动调整 HPA 参数
Agent: [SF | Gap≈65 | out-of-scope]
Agent: 这个任务需要访问你的 K8s 集群 API，我没有这个工具访问权限。建议：
       1. 拆解为：先让我设计 HPA 调整策略，再你来执行
       2. 或配置 kubectl 工具访问后重试
```

---

## 主动触发

你也可以在任何时候主动要求走 SkillForge 流程：

- "按 SkillForge 流程分析这个任务"
- "先做 Gap 分析，再给方案"
- "强制跑一次 Phase 2，查 Registry"

---

## Phase 4：对用户透明的评估（v0.2.3+）

**用户不会看到任何打分询问**。Phase 4 由 Agent 在下一轮用户消息回溯触发，完全内化：

- 用户明确表达不满 / 要求重做 → 记为 `rating=1`（delta=-40）
- 沉默 / 说"好的" / 提下一任务 / 灰色反馈 → 默认 `rating=3`（delta=0）
- 明确惊喜（"太棒了"）→ `rating=5`（delta=+40，极罕见）

Agent 自动调用 `sf update-l0` 写入 L0 索引（`memory/capability-index.yaml`），你不会看到任何打扰。

---

## 涌现式 Skill 生长（v0.2.6+）

Registry **默认为空**，不预置任何种子 skill。运作方式：

1. 你正常用 Cursor Agent 工作，SkillForge 自动记录每次任务的 task_type 和 rating
2. 同一 task_type 累计 `count ≥ 5` 次时，Forger 自动触发，生成 `memory/self-made/xxx-draft-{date}.md` 草稿
3. Agent 在下次回复中提示你"发现 skill 草稿，路径 ..."
4. 你审核草稿（补充 Workflow / Trigger Conditions），用 `sf push` 入库：

```bash
sf demand-queue                                  # 看距离触发还差多远
sf push memory/self-made/refactoring-draft-2026-04-17.md
```

### task_type 命名粒度（影响 Forger 能否触发）

Agent 在 Phase 4 自主为任务取 snake_case 标签。**命名粒度直接决定 Forger 是否能触发**：

| 类别 | 示例 | 后果 |
|------|------|------|
| ✅ 2-3 词 / 领域+类型 | `refactoring` · `linktree_pipeline` · `figma_to_code` | 同类任务复用标签，count 稳步累积 |
| ❌ 4+ 词 / 含动词 | `video_linktree_analysis_implementation` | 每次命名都不一样，count 永远停 1 |
| ❌ 含项目细节 | `fix_config_path_absolutization` | 换个项目就不匹配，无法累积 |

判断标准：**同类工作换个项目，这个 task_type 还能用吗？** 能 → 合格；不能 → 太具体了。

查看现状：

```bash
sf demand-queue        # 能直接看出有没有过细标签（大量 count=1 就是信号）
```

如果发现已有过细条目，**不要手动改 YAML**（会绕过审计管线）；下次同类任务改用正确的粗粒度标签从 0 累积即可，过细的历史条目作为"教训化石"留存。

---

## 常见问题

**Q：为什么设计任务 Gap 总是很低？**

A：架构设计、文档写作类任务 LLM 训练数据覆盖广，确实 Gap 低。Gap 高的通常是"需要读你的真实代码"、"需要调用外部 API"、"要求结果必须精确无误"这类任务。

**Q：Gap 估算感觉不准确怎么办？**

A：规则里的 Gap 是模型自估。你可以直接告诉 Agent："这个任务的 tool 维度缺口至少 30，重新评估"，它会重新输出标签。系统也会通过 `gap_adjustment` 在重复同类任务时自动校准。

**Q：能自定义 Gap 阈值吗？**

A：能。编辑 `integrations/skillforge.mdc` 里五态表格的 Gap 范围数字即可。

**Q：为什么 `sf list-skills` 返回空？**

A：v0.2.6 起 Registry **默认为空**，是正常行为。等你累积 5 次同类任务后 Forger 会自动生草稿。
