# Cursor 集成指南

> 五分钟让 Cursor Agent 具备 SkillForge 能力

> ⚠ **v0.2.x 重要变化**：SF 标签格式已从 v0.1.x 的 `[SF | tool+30,know+20 → Gap≈35 | ...]` 简化为 **`[SF | Gap≈35 | force-enhance]`**（3 维 prec/reas/tool，仅显示总 Gap）。本文档示例若与 `SKILL.md` 不一致以 `SKILL.md` 为准。

---

## 接入步骤

### 1. 复制规则文件

将 `cursor-rule/skillforge.mdc` 复制到你的项目 `.cursor/rules/` 目录：

```bash
cp cursor-rule/skillforge.mdc your-project/.cursor/rules/skillforge.mdc
```

或者复制到全局规则目录（所有 Cursor 窗口生效）：

```bash
cp cursor-rule/skillforge.mdc ~/.cursor/rules/skillforge.mdc
```

### 2. 重启 Cursor Agent

关闭当前对话窗口，开启新对话，规则自动加载。

---

## 验证是否生效

发送一个任务给 Cursor Agent，回复开头应该出现 SF 标签：

```
[SF | no gap → Gap≈3 | independent | direct execution]
```

如果没有出现，检查：
1. `.cursor/rules/` 目录是否存在该文件
2. 文件开头是否包含 frontmatter（`---` 包裹的配置）
3. 是否是新开的对话（旧对话不会重新加载规则）

---

## SF 标签解读

```
[SF | tool+30,know+20 → Gap≈35 | force-enhance | recommend code-expert, need confirm]
 │    │                   │          │               │
 │    └── 非零缺口维度     └── 总Gap   └── 五态状态    └── 行动说明
 └── SkillForge 标识
```

### 维度简写对照

| 简写 | 全称 | 含义 |
|------|------|------|
| `prec` | Precision | 幻觉风险高、数据必须准确 |
| `crea` | Creativity | 需要原创内容、独特方案 |
| `know` | Domain Knowledge | 专业壁垒高、需要最新信息 |
| `tool` | Tool Usage | 需要调用真实工具、访问 API |
| `reas` | Reasoning | 多步骤推理、复杂逻辑链 |
| `spd` | Speed | 有严格时间/资源限制 |

### 五态状态含义

| 状态 | Gap 范围 | Agent 行为 |
|------|----------|-----------|
| `independent` | < 5 | 直接执行，不打断 |
| `light-hint` | 5-15 | 执行，结束时提示优化空间 |
| `suggest` | 15-30 | 询问是否启用 skill 增强 |
| `force-enhance` | 30-50 | 暂停，要求你确认方案 |
| `out-of-scope` | ≥ 50 | 坦白能力边界，不执行 |

---

## 常见场景

### 设计类任务（Gap 通常较低）

```
你: 帮我设计多租户 RBAC+ABAC 权限系统
Agent: [SF | crea+12,know+10 → Gap≈12 | light-hint | direct, note optimization at end]
...（直接给出设计方案）
```

这是正常的——架构设计类任务 LLM 有大量训练数据，Gap 确实低。

### 实现类任务（Gap 通常较高）

```
你: 在我们的 Go 代码库里实现这套权限系统，对接 PostgreSQL row-level security
Agent: [SF | tool+35,prec+25,know+15 → Gap≈40 | force-enhance | ...]
Agent: 当前能力可能不足以达到最优结果，建议选择增强方案：
       1. 启用 code-expert skill（预计提升到 85 分）
       2. 直接执行（高风险）
```

### 超出能力边界

```
你: 实时分析我们生产环境的 Pod 资源使用，并自动调整 HPA 参数
Agent: [SF | tool+60,know+30 → Gap≈65 | out-of-scope | ...]
Agent: 这个任务需要访问你的 K8s 集群 API，我没有这个工具访问权限。建议：
       1. 拆解为：先让我设计 HPA 调整策略，再你来执行
       2. 或配置 kubectl 工具访问后重试
```

---

## 主动触发

你也可以在任何时候主动要求走 SkillForge 流程：

- "按 SkillForge 流程分析这个任务"
- "先做 Gap 分析，再给方案"
- "必须用 code-expert skill 执行"

---

## 常见问题

**Q：为什么设计任务 Gap 总是很低？**

A：架构设计、文档写作类任务，LLM 训练数据覆盖广，确实 Gap 低。Gap 高的通常是"需要读你的真实代码"、"需要调用外部 API"、"要求结果必须精确无误"这类任务。

**Q：Gap 估算感觉不准确怎么办？**

A：规则里的 Gap 是模型自估。你可以直接告诉 Agent："这个任务的 tool 维度缺口至少 30，重新评估"，它会重新输出标签。

**Q：能自定义 Gap 阈值吗？**

A：能。编辑 `cursor-rule/skillforge.mdc` 里五态表格的 Gap 范围数字即可。
