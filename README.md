# SkillForge

> 在执行任务之前，先自我诊断能力缺口。

Agent 默认的工作方式是"拿到任务就做"。这没有问题，直到它用一个 60 分的能力去做一件需要 90 分的事情，还不告诉你。

SkillForge 在任务执行前插入一个诊断环节：**分析缺口 → 决定是否增强 → 执行 → 评估 → 记忆**。并在每次回复开头输出一行可读的诊断标签：

```
[SF | Gap≈35 | force-enhance]
```

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-159%2F159%20passing-brightgreen.svg)]()
[![Stage](https://img.shields.io/badge/stage-0--4%20complete-blue.svg)]()
[![Version](https://img.shields.io/badge/version-v0.2.9--review-blue.svg)]()

---

## 🎯 快速链接

| 想做什么 | 往哪走 |
|---------|--------|
| 想了解所有接入方式？ | [集成指南](docs/integrations.md) |
| 想了解工作原理？ | [工作原理](docs/how-it-works.md) |
| 想作为 Python 包使用？ | [快速开始](docs/quickstart.md) |
| 想添加自己的 skill？ | [Skill Registry 指南](docs/skill-registry.md) |
| 想调整配置？ | [配置参考](docs/config.md) |
| 想启用 MAR 或向量检索？ | [高级功能（Stage 3-4）](docs/advanced.md) |
| 想贡献代码？ | [贡献指南](CONTRIBUTING.md) |

---

## 核心机制一览

### Gap 五态判断

每个任务从 3 个维度估算 Agent 能力缺口（`prec` Precision / `reas` Reasoning / `tool` Tool+Know），取最大缺口作为总 Gap（v0.2.0 起从 6 维简化为 3 维）：

| Gap 范围 | 状态 | Agent 行为 |
|----------|------|-----------|
| Gap < 5 | `independent` | 直接执行，无提示 |
| 5 ≤ Gap < 15 | `light-hint` | 执行，结束时提示优化空间 |
| 15 ≤ Gap < 30 | `suggest` | 询问是否启用 skill 增强 |
| 30 ≤ Gap < 50 | `force-enhance` | 暂停，要求用户确认增强方案 |
| Gap ≥ 50 | `out-of-scope` | 坦白能力边界，不执行 |

### 三层记忆索引

| 层 | 文件 | Token 开销 | 作用 |
|----|------|-----------|------|
| L0 | `capability-index.yaml` | < 500 tokens | 历史误差校准，Phase 1 预判修正 |
| L1 | `trajectories/{type}/` | < 1K tokens | 按任务类型加载执行轨迹 |
| L2 | `reflections.md` | < 2K tokens | 失败教训注入，避免重蹈覆辙 |

---

## 接入方式

SkillForge 本质是一段 Markdown 格式的行为规则，任何能接受 system prompt 的 Agent 均可使用。

| 环境 | 接入方式 |
|------|---------|
| **Cursor** | 复制 `SKILL.md` → `.cursor/rules/skillforge.mdc`（带 `alwaysApply: true`） |
| **Claude Code** | 复制 `integrations/AGENTS.md` → 项目 `CLAUDE.md` |
| **Codex** | 复制 `integrations/AGENTS.md` → 项目 `AGENTS.md` |
| **任意 LLM API** | 将 `SKILL.md` 内容注入 system prompt |
| **Python 自定义 Agent** | `SkillForgeOrchestrator` Python API |
| **LangChain / CrewAI** | `SkillForgeEngine` 作为 Tool 或 Memory |

完整接入文档 → [集成指南](docs/integrations.md)

### Python 包快速示例

```bash
pip install -e .
```

```python
from skillforge import SkillForgeOrchestrator

orch = SkillForgeOrchestrator(registry_path="skillforge-registry.yaml")
result = orch.run(task_description="...", llm_response=llm_json)
closed = orch.evaluate_and_close(result, actual_score=75)
```

### CLI 工具

```bash
skillforge analyze "帮我实现用户权限系统"
skillforge dashboard
```

---

## 开发进度

| Stage | 内容 | 状态 |
|-------|------|------|
| Stage 0 | pyproject.toml · CLI · 包结构 · 种子 skill | ✅ |
| Stage 1 | Phase 1-4 串联 · L0/L1/L2 记忆 · 移动平均校准 | ✅ |
| Stage 2 | observability tracing · sandbox 执行 | ✅ |
| Stage 3 | MAR 多角色辩论 · 向量语义检索 · 混合召回 | ✅ |
| Stage 4 | Reflexion Memory · 历史反思自动注入 Phase 1 | ✅ |
| Stage 5 | CapBound 白盒预判（hidden state 分类） | 规划中 |

---

## 测试

```bash
python3 -m pytest tests/ -q
# 共 159 个测试，全部通过
# 含 CWD 独立性集成测试（v0.2.8+）/ 涌现式 Forger 测试（v0.2.6+）/ update-l0 helper 测试（v0.2.3+）
```

---

## 致谢与学术依据

SkillForge 的设计从以下研究中提取了核心思路：

**[KnowSelf](https://arxiv.org/abs/2502.04563) — ACL 2025**  
发现 Agent 采用"漫灌"策略，不先判断自己缺什么就执行。提供了"情境判断"的理论依据，启发了 SkillForge 的五态 Gap 分级设计（独立/轻提示/建议增强/强制增强/超边界）。

**[CapBound](https://arxiv.org/abs/2504.02419) — 清华 & 蚂蚁集团**  
发现 LLM hidden states 中，"能做到"和"做不到"的任务在 98%+ 准确率下线性可分，且模型自己知道边界在哪里。启发了 Phase 1 的能力预判机制；白盒路径（直接读 hidden states）列为 Stage 5 研究课题。

**[Reflexion](https://arxiv.org/abs/2303.11366) — NeurIPS 2023**  
用自然语言反思替代梯度更新，HumanEval pass@1 提升 6.2 分。SkillForge 的 L2 反思日志和 Stage 4 ReflectionLoader 直接对应这个机制，实现了"下次同类任务自动加载历史教训"的闭环。

**[MAR / Multi-Agent Reflexion](https://arxiv.org/abs/2402.07927) — Ozer et al.**  
多角色批评辩论解决单 Agent 自评的确认偏误问题。对应 Stage 3 的 MARCoordinator：三个 Critic（Optimist/Skeptic/Domain Expert）+ Judge 在单次 LLM 调用内完成，避免多次往返的 token 开销。

**[Hermes Agent](https://arxiv.org/abs/2407.00418)**  
失败后自动生成可复用的 SKILL.md 文件。对应 SkillForge-Forger 模块：同一类任务成功 3 次后自动生成 skill 草稿，要求用户审核后入库。

---

## 许可证

[Apache 2.0](LICENSE)

---

Made by [@kroxchan](https://github.com/kroxchan)
