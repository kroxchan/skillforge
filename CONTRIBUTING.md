# Contributing to SkillForge

感谢你关注 SkillForge！本指南将帮助你了解如何参与贡献。

---

## 快速开始

```bash
# 1. Fork 并克隆
git clone https://github.com/your-username/skillforge.git
cd skillforge

# 2. 创建虚拟环境（Python >= 3.11）
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 运行测试
pytest tests/ -q
# 全部 159 测试通过（v0.2.9-review 基线）
```

---

## 开发流程

### 1. 创建功能分支

从 `main` 分支创建有意义的分支名：

```bash
git checkout -b feature/your-feature-name
# 或
git checkout -b fix/issue-description
```

### 2. 编写代码

遵守以下规范：

- **类型提示**：所有公开函数和类必须有完整的类型注解
- **文档字符串**：公共 API 需编写 Google-style docstring
- **单职原则**：每个函数只做一件事
- **测试覆盖**：新功能必须有对应测试

```python
class EnhancementDecider:
    def decide(
        self,
        gap: float,
        predicted_score: float,
        recommendations: list[SkillRecommendation],
    ) -> Decision:
        """根据 Gap 值做出五态决策。

        Args:
            gap: 能力缺口值（0-100）
            predicted_score: Phase 1 预估分
            recommendations: 候选 skill 列表

        Returns:
            Decision 对象，包含行动建议和等待确认标志
        """
        ...
```

### 3. 运行检查

```bash
# 代码格式 + lint
ruff check src/

# 类型检查
mypy src/

# 全部测试
pytest tests/ -v
```

### 4. 提交变更

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

类型说明：

| 类型 | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `refactor` | 代码重构（不改变功能） |
| `test` | 测试相关 |
| `perf` | 性能优化 |
| `chore` | 构建/工具变更 |

示例：

```bash
git commit -m "feat(engine): add SkillForgeOrchestrator.run() for phase chaining"
git commit -m "fix(evaluator): correct reflection markdown format for empty errors"
git commit -m "docs: add contributing guide"
```

### 5. 推送并创建 Pull Request

```bash
git push origin feature/your-feature-name
```

在 GitHub 上创建 PR，描述：
- 这个 PR 解决了什么问题
- 做了哪些改动
- 如何测试

---

## 语义版本策略

SkillForge 遵循 [SemVer](https://semver.org/)：

| 版本类型 | 触发条件 |
|----------|----------|
| **patch** | Bug fix，不改变 capability_gains |
| **minor** | 新增 workflow，不破坏原有行为 |
| **major** | 接口变更（如修改 `Decision` 模型字段） |

发布新版本时打 git tag：

```bash
git tag -a v0.2.0 -m "feat: add observability tracing"
git push --tags
```

---

## 架构规范

### 模块职责边界

```
skillforge/
├── engine.py        # Phase 1：预判引擎（纯函数，无副作用）
├── decider.py       # Phase 2：决策逻辑（无 IO）
├── executor.py      # Phase 3：执行器（Prompt 构建，无真实执行）
├── evaluator.py     # Phase 4：评估 + 记忆闭环（有文件 IO）
├── registry.py      # Skill 注册表（有文件 IO）
├── indexer.py       # L0 Capability Index（有文件 IO）
└── cli.py           # CLI 入口（组合以上所有模块）
```

**原则**：
- `engine` / `decider` 无文件 IO，可独立测试
- `evaluator` / `registry` / `indexer` 操作文件，全部通过构造函数注入路径
- 所有模块均导出快捷函数（如 `quick_analyze`、`decide_enhancement`）

### 三层记忆架构

```
L0 capability-index.yaml   <500 tokens  Agent 启动时注入
L1 memory/trajectories/    <1K tokens   Phase 2 前按 task_type 加载
L2 memory/reflections.md   <2K tokens   Phase 4 前读取，不注入 prompt
```

---

## 新增 Skill 指南

v0.2.6 起 Registry 改为**涌现式生长**，优先通过 Forger 自动生成草稿：

```bash
sf demand-queue         # 查看距 Forger 阈值（count ≥ 5）还差多远
sf forge                # 查看哪些 task_type 可触发
sf push memory/self-made/xxx-draft-2026-04-17.md    # 审核草稿后入库
```

如需手动添加，Registry entry 格式（v0.2.0+ 只保留 3 维 capability_gains）：

```yaml
- skill_id: my-new-skill
  name: My New Skill
  domain: [your_domain]
  task_types: [your_task_type]
  capability_gains:
    precision: 10
    reasoning: 5
    tool_knowledge: 10
  quality_tier: "L2"        # L1=轻量，L2=标准，L3=专业
  avg_effectiveness: 0.7    # 新 skill 默认 0.7，使用后 EMA 自动校准
  source: local             # local / community / autoforge
```

> ⚠ 旧字段 `creativity` / `speed` / `domain_knowledge` / `tool_usage` 已在 v0.2.0 废弃，若出现会被忽略。

推荐通过 CLI 添加（自动校验格式）：

```bash
sf push ./my-new-skill/SKILL.md
```

---

## 报告问题

Bug 报告请包含：

1. 环境：`python --version` + OS
2. 复现步骤（最小可复现用例）
3. 预期行为 vs 实际行为
4. 相关日志或截图

---

## 许可证

贡献即表示你同意你的代码遵循 [Apache 2.0 许可证](../LICENSE)。

---

## 常见问题

**Q: 为什么我的 PR 被要求修改测试？**
A: SkillForge 要求所有功能有测试覆盖，且测试必须通过 CI。

**Q: 可以添加新的 Phase 吗？**
A: 可以，但需要更新 `SkillForgeOrchestrator.run()` 的串联逻辑，并通过 ADR（架构决策记录）记录设计理由，参考 `DEVLOG.md` 中的 ADR 格式。

**Q: 如何测试需要 LLM 的功能？**
A: Phase 1 的 LLM 调用通过 `SkillForgeEngine.parse_analysis()` 解析，测试中使用模拟 JSON 字符串注入，不依赖真实 LLM。
