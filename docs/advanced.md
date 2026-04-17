# 高级功能（Stage 3 & 4）

> MAR 多角色辩论 · 向量语义检索 · Reflexion Memory

---

## Stage 3：MAR 多角色辩论评估

### 为什么需要 MAR？

Phase 4 的默认 rating 识别（v0.2.3 起 actual=predicted 基线）在复杂任务上可能漏掉真实质量问题——Agent 和用户都倾向于"能跑就行"。MAR（Multi-Agent Reflexion）引入三个不同角色的批评者作为**可选补充**，解决"思维退化"问题：

| 角色 | 立场 | 输出 |
|------|------|------|
| Optimist | 找优点，防止过度自我批评 | 一行：做对了什么 |
| Skeptic | 找漏洞，发现潜在问题 | 一行：可能出错的地方 |
| Domain Expert | 检查领域盲点 | 一行：专业陷阱 |
| Judge | 综合三方，给出最终决策 | 校准分 + 核心教训 + 是否触发改进 |

三个 Critic + Judge **合并为单次 LLM 调用**（role-play 内嵌 prompt），避免多次往返的 token 开销。

### 启用 MAR

**config.yaml**：

```yaml
stage3:
  mar:
    enabled: true
    provider: "llm-only"      # 降级模式，使用配置的 LLM
    llm_endpoint: ""           # 留空则使用 OPENAI_API_KEY
    llm_model: "gpt-4o-mini"
```

**Python API**：

```python
orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    mar_enabled=True,
)

result = orch.run(task_description="...", llm_response=llm_json)
closed = orch.evaluate_and_close(result, user_rating=3)   # actual = predicted 自动推导

# MAR 结果
mar = closed.phase4.mar_result
print(mar["optimist"])                       # "代码结构清晰，并发设计合理"
print(mar["skeptic"])                        # "缺少超时和重试机制"
print(mar["domain_expert"])                  # "未考虑反爬策略"
print(mar["judge"]["final_score"])           # 72
print(mar["judge"]["lesson"])                # "网络 IO 任务必须加超时机制"
print(mar["judge"]["trigger_improvement"])   # True
```

### 在 Cursor 环境中使用 MAR

Cursor 环境下无需额外 API key，Task tool 直接承接：

```yaml
stage3:
  mar:
    enabled: true
    provider: "cursor"   # 零额外费用
```

注意：`provider: "cursor"` 需要在 Cursor agent session 中运行 SkillForge，由 Cursor 的 Task tool 实现 multi-agent 调度。

---

## Stage 3：向量语义检索

### 为什么需要向量检索？

关键词匹配只能覆盖约 60% 的场景——当任务描述和 skill 触发词语义相近但词形不同时（如"构建爬虫" vs "写采集脚本"），关键词匹配会遗漏。HybridSkillMatcher 双路召回解决这个问题：

```
查询 → 关键词匹配（精确）+ 向量检索（语义）→ 加权合并 → Top-K 推荐
```

### Mock 模式（零依赖，开发调试用）

默认使用 Mock 实现，不需要安装任何额外依赖：

```yaml
stage3:
  vector_search:
    enabled: true
    provider: "mock"
```

Mock 基于词形重叠打分，能跑通整个流程，但不是真正的向量检索。

### ChromaDB 模式（真实语义检索）

```bash
pip install chromadb sentence-transformers
```

```yaml
stage3:
  vector_search:
    enabled: true
    provider: "chroma"
    chroma:
      persist_dir: ".chroma/"
      model: "all-MiniLM-L6-v2"   # 本地 embedding 模型，首次自动下载
      distance_metric: "cosine"
    keyword_weight: 0.6
    semantic_weight: 0.4
```

**Python API**：

```python
orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    vector_search_enabled=True,
)

# Phase 2 自动走混合检索
result = orch.run(
    task_description="帮我构建一个数据采集系统",  # "采集" 在 Registry 里没有触发词
    llm_response=llm_json,
)
# 向量检索会找到 code-expert-skill（因为语义相近），关键词匹配可能找不到
```

### 手动使用 HybridSkillMatcher

```python
from skillforge import SkillRegistry, HybridSkillMatcher, create_vector_search

registry = SkillRegistry("skillforge-registry.yaml")
provider = create_vector_search(provider="mock")  # 或 "chroma"
provider.add_skills(registry.list_skills())

matcher = HybridSkillMatcher(
    registry_skills=registry.list_skills(),
    vector_search=provider,
    keyword_weight=0.6,
    semantic_weight=0.4,
)

results = matcher.search("帮我写一个数据采集脚本", task_type="code_generation", top_k=3)
for rec in results:
    print(f"{rec.skill.name}: {rec.match_score:.2f} ({rec.reason})")
```

---

## Stage 4：Reflexion Memory 重试闭环

### 机制

```
任务 A 失败（rating=1, delta=-40）
  → sf update-l0 自动追加反思模板骨架到 L2 reflections.md
  → Agent 按内因三维度填充（理解 / 预判 / 执行策略）

任务 B（同 task_type，下次）
  → Phase 1 前自动加载同类型反思
  → Agent 知道"上次在这里翻过车"
  → 预判更准，执行更谨慎
```

### 启用

```yaml
stage4:
  reflexion:
    enabled: true
    max_entries: 5              # 最多注入 5 条历史反思
    min_delta_threshold: -5.0   # 只加载 delta < -5 的失败
    max_age_days: 90            # 90 天内的反思
```

**Python API**：

```python
orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    reflexion_enabled=True,
)
```

### 查看 Reflexion 状态

```python
from skillforge.reflexion import ReflectionLoader

loader = ReflectionLoader(memory_dir="memory", min_delta_threshold=-5.0, enabled=True)

# 统计
stats = loader.get_stats()
print(f"总反思条数: {stats['total']}")
print(f"按类型分布: {stats['by_task_type']}")

# 获取 code_generation 类型的历史教训
lessons = loader.get_recent_lessons("code_generation", limit=3)
for lesson in lessons:
    print(f"- {lesson}")

# 获取历史失败根因
causes = loader.get_failure_root_causes("code_generation", limit=5)
```

### Reflexion 注入上下文格式

Phase 1 注入的上下文（存储在 `phase1.capability_dimensions["_l2_reflection_context"]`）：

```
[L2 Reflexion - code_generation]
  1. [sf-abc123] Delta=-15 | 异步任务必须加超时和重试机制
  2. [sf-def456] Delta=-8  | API 开发需先做好参数校验
```

---

## 同时启用全部 Stage 3 & 4

```python
orch = SkillForgeOrchestrator(
    registry_path="skillforge-registry.yaml",
    memory_dir="memory",
    mar_enabled=True,
    vector_search_enabled=True,
    reflexion_enabled=True,
)
```

三个组件各自独立，互不依赖，均可单独开启。默认全部关闭，不影响基础 Phase 1-4 流程。

### Token 开销估算

| 组件 | 额外 Token / 任务 | 触发条件 |
|------|-----------------|---------|
| MAR | ~1,000 | 仅在 rating=1（delta=-40）时触发，约 10% 任务 |
| 向量检索 | ~200 | Phase 2 每次都跑，但只是本地计算 |
| Reflexion | ~200 | Phase 1 有同 task_type 历史反思时 |
| 合计（平均） | ~400 | 远低于 1K tokens/任务 |
