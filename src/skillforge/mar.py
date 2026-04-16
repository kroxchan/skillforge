# SkillForge Stage 3: MAR Multi-Agent Reflexion
# 基于 Cursor/Codex/Claude Code 的原生 Task tool，零额外 API key 依赖
#
# 支持环境（需有多 agent 工作模式）：
#   - Cursor IDE（Task tool / subagent_type）
#   - Claude Code（claude code --mention / multi-agent）
#   - Codex（ Agents SDK）
#
# 功能说明：
#   - 仅在 config.yaml 中 stage3.mar.enabled: true 时启用
#   - 默认关闭，不影响现有 Phase 1-4 流程
#   - Token 优先：单次调用 + role-play，同一 context window 内完成三 Critic 评估

from typing import Optional
from skillforge.models import Phase4Result, Reflection, Trajectory

# ── Prompt 模板 ──────────────────────────────────────────────
#
# 设计原则：
#   1. 单次 LLM 调用完所有 Critic 评估（role-play + JSON 输出）
#      避免 3 次往返，节省 2/3 token
#   2. 三个 Critic 视角互补：优点 / 漏洞 / 盲点
#   3. Judge 综合结论包含 delta 修正建议，供 Phase 1 下次校准

MAR_PROMPT_TEMPLATE = """你是一次代码任务的事后审查会议。三个角色同时评估，不互相讨论。

## 任务信息
任务类型: {task_type}
任务描述: {task_description}
Phase 1 预估分: {predicted_score}
Phase 4 实际分: {actual_score}
Delta: {delta}

## 你的评估（同时完成三个角色的任务）

### 角色 1：优点发现者（Optimist）
在 {task_type} 任务中，这个执行结果做对了什么？
输出一行优点。

### 角色 2：漏洞发现者（Skeptic）
在 {task_type} 任务中，这个执行结果哪里可能出错或可以更好？
输出一行漏洞描述。

### 角色 3：盲点检查员（Domain Expert）
{task_type} 领域有哪些常见陷阱这次执行没有覆盖？
输出一行盲点。

### 裁判（Judge，综合决策）
结合以上三个视角：
1. 最终评分（微调 Phase 4 的 actual_score，如无大偏差则保持）
2. delta 校准（本次预估偏高了还是偏低了？调整多少下次更准？）
3. 核心教训（一句话，存入 L0 索引）
4. 是否触发 SkillForge 自改进？（是/否）

请以 JSON 格式输出：
{{
  "optimist": "优点描述（≤20字）",
  "skeptic": "漏洞描述（≤30字）",
  "domain_expert": "盲点描述（≤30字）",
  "judge": {{
    "final_score": 实际调过的分数,
    "delta_adjustment": 校准值（正=下次应高估，负=下次应低估）,
    "lesson": "核心教训（≤50字）",
    "trigger_improvement": "是" 或 "否",
    "improvement_note": "改进说明（如 trigger_improvement=否 则为空）"
  }}
}}
"""


def build_mar_prompt(trajectory: Trajectory, phase4: Phase4Result) -> str:
    """构建 MAR 评估 prompt"""
    delta = phase4.actual_score - trajectory.phase1.predicted_score
    return MAR_PROMPT_TEMPLATE.format(
        task_type=trajectory.task_type,
        task_description=trajectory.task_description[:120],
        predicted_score=trajectory.phase1.predicted_score,
        actual_score=phase4.actual_score,
        delta=f"{delta:+.1f}",
    )


def parse_mar_response(raw: str) -> dict:
    """
    解析 MAR LLM 返回的 JSON。
    支持 markdown code fence 和裸 JSON。
    """
    import json, re

    stripped = raw.strip()
    # 去掉 markdown code fence
    fenced = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.MULTILINE)
    fenced = re.sub(r"\s*```$", "", fenced, flags=re.MULTILINE)

    try:
        return json.loads(fenced.strip())
    except json.JSONDecodeError:
        # 兜底：找第一对 {}
        first = stripped.find("{")
        last = stripped.rfind("}")
        if first >= 0 and last > first:
            try:
                return json.loads(stripped[first : last + 1])
            except json.JSONDecodeError:
                pass
    return {}


# ── 抽象 Task Tool 接口 ───────────────────────────────────────
#
# 支持三种调用方式（按环境自动检测）：
#   1. Cursor IDE    → Task tool（Task() 调用）
#   2. Claude Code  → subprocess / claude code --mention
#   3. Codex        → Agents SDK
#   4. 无环境        → 直接 LLM 调用（降级）
#
# 用户需要的选择：
#   - stage3.provider: "cursor" | "claude-code" | "codex" | "llm-only"
#   - stage3.llm_endpoint: （当 provider=llm-only 时）自定义 LLM 端点


class TaskToolAdapter:
    """
    抽象层：统一 Task tool 调用接口。
    根据配置选择实际执行方式。
    """

    def __init__(
        self,
        provider: str = "llm-only",
        llm_endpoint: Optional[str] = None,
        model: str = "auto",
    ):
        self.provider = provider
        self.llm_endpoint = llm_endpoint
        self.model = model

    def run(self, prompt: str, subagent_type: str = "generalPurpose") -> str:
        """
        执行 prompt，返回 LLM 输出。
        provider=llm-only 时直接调 LLM；
        其余在 Cursor/Claude Code/Codex 环境中由上层 Agent 调用。
        """
        if self.provider == "llm-only":
            return self._call_llm(prompt)
        else:
            # Cursor/Claude Code/Codex 环境由父 Agent 接管
            # 这里只生成提示信息，实际执行由环境注入
            raise NotImplementedError(
                f"provider={self.provider} 需要在对应 IDE 环境中运行。"
                f"请在 {self.provider} 的 agent session 中调用 SkillForge MAR。"
            )

    def _call_llm(self, prompt: str) -> str:
        """直接 LLM 调用（llm-only 模式或测试）"""
        import os, httpx

        if not self.llm_endpoint:
            # 默认用 OpenAI compatible endpoint（需配置 OPENAI_API_KEY）
            api_key = os.environ.get("OPENAI_API_KEY", "")
            endpoint = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
            model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        else:
            api_key = os.environ.get("MAR_API_KEY", "")
            endpoint = self.llm_endpoint
            model_name = self.model

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 600,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(endpoint, json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"MAR LLM 调用失败: {e}")


# ── MAR 协调器 ────────────────────────────────────────────────

class MARCoordinator:
    """
    多角色辩论评估协调器。

    使用方式（config 中启用）：
        config.stage3.mar.enabled = True
        config.stage3.mar.provider = "cursor"  # 或 "claude-code" / "codex" / "llm-only"

    Token 优化策略：
        1. 单次调用：三个 Critic + Judge 合并为一次 LLM 请求
        2. role-play 内嵌 prompt，不做多次往返
        3. JSON 输出结构化，避免自由文本解析开销
    """

    def __init__(
        self,
        enabled: bool = False,
        provider: str = "llm-only",
        llm_endpoint: Optional[str] = None,
        model: str = "auto",
    ):
        self.enabled = enabled
        self._adapter = TaskToolAdapter(provider=provider, llm_endpoint=llm_endpoint, model=model)

    def evaluate(self, trajectory: Trajectory, phase4: Phase4Result) -> dict:
        """
        执行 MAR 多角色评估。

        Args:
            trajectory: 完整执行轨迹
            phase4: Phase 4 评估结果

        Returns:
            {
                "optimist": str,
                "skeptic": str,
                "domain_expert": str,
                "judge": {
                    "final_score": float,
                    "delta_adjustment": float,
                    "lesson": str,
                    "trigger_improvement": bool,
                    "improvement_note": str,
                },
                "raw": str,  # 原始 LLM 输出
            }
        """
        if not self.enabled:
            return self._dummy_result(phase4.actual_score)

        prompt = build_mar_prompt(trajectory, phase4)

        try:
            raw = self._adapter.run(prompt)
        except NotImplementedError:
            # 非 Cursor/Claude Code/Codex 环境，降级
            return self._dummy_result(phase4.actual_score)

        parsed = parse_mar_response(raw)

        return {
            "optimist": parsed.get("optimist", ""),
            "skeptic": parsed.get("skeptic", ""),
            "domain_expert": parsed.get("domain_expert", ""),
            "judge": {
                "final_score": parsed.get("judge", {}).get("final_score", phase4.actual_score),
                "delta_adjustment": parsed.get("judge", {}).get("delta_adjustment", 0.0),
                "lesson": parsed.get("judge", {}).get("lesson", ""),
                "trigger_improvement": parsed.get("judge", {}).get("trigger_improvement", "否") == "是",
                "improvement_note": parsed.get("judge", {}).get("improvement_note", ""),
            },
            "raw": raw,
        }

    @staticmethod
    def _dummy_result(actual_score: float) -> dict:
        """MAR 未启用时的兜底返回"""
        return {
            "optimist": "(MAR 未启用)",
            "skeptic": "(MAR 未启用)",
            "domain_expert": "(MAR 未启用)",
            "judge": {
                "final_score": actual_score,
                "delta_adjustment": 0.0,
                "lesson": "",
                "trigger_improvement": False,
                "improvement_note": "",
            },
            "raw": "",
        }

    def build_cursor_prompt(self, trajectory: Trajectory, phase4: Phase4Result) -> str:
        """
        生成在 Cursor IDE 中手动运行的 prompt。
        用于 provider=cursor 时，由用户在 Cursor agent session 中粘贴执行。
        """
        return build_mar_prompt(trajectory, phase4)
