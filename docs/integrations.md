# 集成指南

> SkillForge 是通用的 Agent 行为规则，不绑定任何特定 IDE 或框架。
> 本质是一段 Markdown 格式的系统提示词，任何能接受 system prompt 的 Agent 都可以接入。

---

## 接入方式总览

| 环境 | 接入文件 | 位置 |
|------|---------|------|
| **Cursor** | `skillforge.mdc` | `.cursor/rules/` 或 `~/.cursor/rules/` |
| **Claude Code** | `CLAUDE.md` | 项目根目录或 `~/.claude/CLAUDE.md` |
| **Codex** | `AGENTS.md` | 项目根目录 |
| **OpenAI Assistants / 任意 LLM** | 直接注入 `SKILL.md` 内容 | 系统提示词 |
| **Python 自定义 Agent** | `SkillForgeOrchestrator` | Python API |
| **LangChain / CrewAI** | `SkillForgeEngine` | 作为 Tool 或 Memory |

---

## Cursor

复制 `integrations/skillforge.mdc` 到：

```bash
# 单项目生效
cp integrations/skillforge.mdc your-project/.cursor/rules/skillforge.mdc

# 全局生效（所有 Cursor 窗口）
cp integrations/skillforge.mdc ~/.cursor/rules/skillforge.mdc
```

重启 Cursor Agent 后，每次回复开头会出现 SF 标签：

```
[SF | no gap → Gap≈3 | independent | direct execution]
```

规则文件开头的 frontmatter（`alwaysApply: true`）控制自动加载行为。详见 [Cursor 集成细节](cursor-integration.md)。

---

## Claude Code

复制 `integrations/AGENTS.md` 内容到：

```bash
# 单项目生效
cp integrations/AGENTS.md your-project/CLAUDE.md

# 全局生效（所有 Claude Code session）
cat integrations/AGENTS.md >> ~/.claude/CLAUDE.md
```

Claude Code 在每次 session 开始时自动读取项目根目录的 `CLAUDE.md`。

---

## Codex

```bash
cp integrations/AGENTS.md your-project/AGENTS.md
```

Codex 在每次任务开始时读取项目根目录的 `AGENTS.md`。

---

## OpenAI Assistants API / 任意 LLM

将 `SKILL.md` 或 `integrations/AGENTS.md` 的内容添加到系统提示词：

```python
import openai
from pathlib import Path

skill_content = Path("SKILL.md").read_text()

response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
            "role": "system",
            "content": f"你是一个 AI 助手。以下是你的行为规则：\n\n{skill_content}"
        },
        {
            "role": "user",
            "content": "帮我写一个 Python 异步爬虫"
        }
    ]
)
```

也可以只注入核心规则（节省 token），从 `SKILL.md` 里提取五态判断和输出格式部分即可。

---

## Python 自定义 Agent

使用 `SkillForgeOrchestrator` 完整接管 Phase 1-4：

```python
from skillforge import SkillForgeOrchestrator, PHASE1_PROMPT_TEMPLATE

orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    reflexion_enabled=True,
)

# 1. 构建 Phase 1 分析 prompt
engine_prompt = orch.evaluator  # 获取 prompt 模板
phase1_prompt = PHASE1_PROMPT_TEMPLATE.format(task_description="帮我写一个异步爬虫")

# 2. 用你的 LLM 调用 Phase 1
llm_response = your_llm.complete(phase1_prompt)  # 返回 JSON 字符串

# 3. 跑完整流程
result = orch.run(
    task_description="帮我写一个异步爬虫",
    llm_response=llm_response,
    user_decision="auto",
)

# 4. 用增强后的 context 执行任务
final_output = your_llm.complete(result.phase3_context)

# 5. Phase 4 闭环（传入实际质量分）
closed = orch.evaluate_and_close(result, actual_score=78)
```

---

## LangChain 集成

将 SkillForge 包装为 LangChain Tool：

```python
from langchain.tools import Tool
from skillforge import SkillForgeEngine

engine = SkillForgeEngine()

def skillforge_analyze(task_description: str) -> str:
    """Phase 1 分析：返回 Gap 评估和增强建议"""
    prompt = engine.build_prompt(task_description)
    # 调用你的 LLM 获取分析结果
    return prompt  # 返回 prompt 供 LangChain agent 使用

skillforge_tool = Tool(
    name="skillforge_gap_analysis",
    func=skillforge_analyze,
    description="分析任务难度和 Agent 能力缺口，决定是否需要 skill 增强"
)

# 注入 LangChain agent
from langchain.agents import AgentExecutor
agent = AgentExecutor(tools=[skillforge_tool, ...], ...)
```

---

## CrewAI 集成

将 SkillForge 作为前置任务（Pre-task）：

```python
from crewai import Task, Agent
from skillforge import SkillForgeOrchestrator
import json

orch = SkillForgeOrchestrator(registry_path="skillforge-registry.yaml")

def skillforge_precheck(task_description: str, llm_analysis: str) -> dict:
    """在 CrewAI 任务执行前运行 SkillForge 诊断"""
    result = orch.run(
        task_description=task_description,
        llm_response=llm_analysis,
        user_decision="auto",
    )
    return {
        "gap_state": result.decision.action,
        "enhanced_context": result.phase3_context,
        "recommended_skills": [r.skill.name for r in result.decision.options],
    }
```

---

## 验证是否生效

不论哪种接入方式，给 Agent 发送一个任务，回复开头应该出现：

```
[SF | ... → Gap≈... | ... | ...]
```

没有出现说明规则未加载。检查：
1. 文件是否在正确位置
2. 是否开启了新的 session（旧 session 不会重新加载）
3. 对于 OpenAI API 方式，检查 system prompt 是否包含规则内容

---

## 各环境 Token 开销对比

| 接入方式 | 规则注入 token | 每任务额外 token | 备注 |
|---------|------------|--------------|------|
| Cursor `.mdc` | ~600 | ~50（SF 标签） | alwaysApply 每次对话注入一次 |
| Claude Code `CLAUDE.md` | ~600 | ~50 | session 开始时注入 |
| Codex `AGENTS.md` | ~600 | ~50 | 任务开始时注入 |
| System prompt 注入 | 600-1500 | ~50 | 取决于注入 SKILL.md 还是精简版 |
| Python API | 0（不注入规则）| 0 | 由代码直接控制，无 prompt overhead |
