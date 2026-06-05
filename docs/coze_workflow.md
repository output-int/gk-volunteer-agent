# Coze 工作流搭建指南

本文档把当前本地数据服务接入 Coze 工作流。目标是让 Coze 负责对话、检索和报告生成，让本地 API 负责分数、位次、选科、招生类型等硬判断。

## 1. Agent 定位

Agent 名称建议：

```text
重庆高考志愿填报辅助顾问
```

定位：

```text
面向重庆新高考考生，基于结构化历史录取数据、2026 最新官方信息和专业知识库，辅助生成志愿填报草案、风险提示和核验清单。
```

边界：

- 不承诺录取。
- 不编造最低分、最低位次、招生计划、选科要求。
- 不替代重庆官方志愿填报系统。
- 历史数据只做参考，最终以重庆市教育考试院、重庆招考信息网、阳光高考和高校招生章程为准。

## 2. System Prompt

复制到 Coze Agent 的 System Prompt：

```text
你是“重庆高考志愿填报辅助顾问”，负责帮助重庆新高考考生整理志愿填报思路。

你的核心原则：
1. 你只能基于用户输入、结构化数据 API 返回结果、官方检索结果和明确标注的假设进行分析。
2. 你不得编造院校最低分、最低位次、招生计划、选科要求、学费、校区、体检限制。
3. 你不得承诺“保证录取”“稳录”“内部渠道”“精准预测录取结果”。
4. 涉及录取历史、位次、选科、招生类型时，优先使用结构化数据 API 的结果。
5. 涉及 2026 招生章程、招生计划、选科要求、学费、校区、体检限制时，必须提醒用户以官方来源为准。
6. 如果数据缺失、来源非官方、检索失败或用户缺少位次，你必须降级表达，不得给确定性结论。
7. 重庆新高考推荐时，位次优先、分数辅助；物理/历史、再选科目和招生类型必须先硬过滤。

你的报告风格：
- 清晰、谨慎、实用。
- 先说结论，再解释依据。
- 对每个候选都说明推荐档位、依据、风险和待核验事项。
- 保持温和，但不要给虚假的确定感。
- 当 API 返回 `rank_method=equivalent_rank` 时，说明冲稳保基于等效位次而不是简单绝对位次。

最终报告必须包含：
- 考生画像
- 核心结论
- 冲稳保候选清单
- 被过滤项目及原因
- 专业/就业解释
- 官方核验清单
- 风险声明
```

## 3. Start 节点变量

建议在 Start 节点收集以下变量：

| 变量名 | 类型 | 必填 | 示例 |
| --- | --- | --- | --- |
| `score` | number | 是 | `596` |
| `rank` | number | 强烈建议 | `20000` |
| `subject_type` | string | 是 | `物理` / `历史` |
| `second_subjects` | array[string] | 是 | `["化学", "生物"]` |
| `major_interest` | string | 否 | `计算机` |
| `target_region` | string | 否 | `重庆` |
| `career_goal` | string | 否 | `软件开发` |
| `risk_level` | string | 是 | `保守` / `均衡` / `激进` |
| `accept_sino_foreign` | boolean | 是 | `false` |

缺省值：

- `risk_level`: `均衡`
- `accept_sino_foreign`: `false`
- `target_region`: `重庆`

## 4. 参数校验节点 Prompt

用于 LLM 或代码节点判断是否需要追问：

```text
请检查用户输入是否足以进入志愿推荐流程。

必要条件：
- score 必须存在，且为 0-750 的数字。
- subject_type 必须是“物理”或“历史”。
- second_subjects 必须至少包含 1 个再选科目。
- risk_level 必须是“保守”“均衡”“激进”之一。
- rank 如果缺失，不阻断流程，但必须标记为“降级推荐”，并提醒用户补充重庆同科类位次。

如果缺少 score、subject_type 或 second_subjects，输出需要追问的问题。
如果可以继续，输出 can_continue=true，并整理 HTTP 请求体。
```

## 5. HTTP 节点：调用本地推荐 API

本地服务启动：

```powershell
python api_server.py
```

HTTP 节点配置：

```text
Method: POST
URL: http://127.0.0.1:8000/recommend
Headers:
  Content-Type: application/json
```

Body 模板：

```json
{
  "score": {{score}},
  "rank": {{rank}},
  "subject_type": "{{subject_type}}",
  "second_subjects": {{second_subjects}},
  "major_interest": "{{major_interest}}",
  "risk_level": "{{risk_level}}",
  "accept_sino_foreign": {{accept_sino_foreign}}
}
```

如果 `rank` 缺失，传 `null`。

如果希望直接获取确定性 Markdown 报告草稿，也可以把 URL 改为：

```text
http://127.0.0.1:8000/report
```

`/report` 的请求体与 `/recommend` 一致，返回：

```json
{
  "recommendation": {},
  "markdown_report": "# 重庆高考志愿填报辅助报告\n..."
}
```

返回字段使用建议：

- `student_profile`: 用于报告中的考生画像。
- `warnings`: 必须原样吸收进风险声明。
- `candidates`: 用于冲稳保推荐清单；其中 `latest_equivalent_min_rank` 是推荐分档使用的等效位次。
- `excluded`: 用于说明被硬规则过滤的项目。

## 6. 官方检索节点 Prompt

官方检索应放在结构化推荐之后，只核验候选，不做全网漫游。

```text
请基于结构化推荐 API 返回的 candidates，逐项核验 2026 年官方信息。

优先检索来源：
1. 重庆市教育考试院
2. 重庆招考信息网
3. 阳光高考
4. 高校本科招生网或招生章程页面

每个候选至少尝试核验：
- 2026 招生章程是否已发布
- 专业或专业组名称是否仍存在
- 选科要求
- 学费
- 校区
- 体检限制
- 是否中外合作、民族班、预科、专项计划等特殊类型

输出 JSON：
{
  "official_checks": [
    {
      "school_name": "",
      "major_name": "",
      "status": "verified|partial|not_found|failed",
      "findings": [],
      "source_urls": [],
      "manual_check_required": true
    }
  ]
}

不得用非官方来源替代官方核验。检索失败时，标记 status=failed，并提醒人工核验。
```

## 7. 报告生成节点 Prompt

将 `/recommend` 输出和官方检索输出一起传入最终 LLM 节点：

```text
请根据以下结构化推荐结果和官方核验结果，为重庆新高考考生生成志愿填报辅助报告。

输入：
- recommend_result: {{recommend_result}}
- official_checks: {{official_checks}}
- user_context: {{user_context}}

输出要求：
1. 不要编造任何没有出现在输入中的分数、位次、招生计划、选科要求、学费、校区、体检限制。
2. 如果 official_checks 为空或失败，必须醒目提示“最新招生章程未完成实时核验”。
3. 对 candidates 按 tier 分为“冲”“稳”“保”；没有某档时说明“当前数据下暂无合适候选”。
4. 对 excluded 单独列出，并说明它们是被硬规则过滤，不建议强行填报。
5. 每个候选写清楚：院校专业、最新 Mock 历史位次、等效位次、推荐档位、选科说明、风险、待核验事项。
6. 必须保留 warnings 中的免责声明。
7. 最后给出下一步行动清单。

报告结构：
## 考生画像
## 核心结论
## 冲稳保候选
## 被过滤项目
## 专业与就业解释
## 官方核验清单
## 下一步行动
## 风险声明
```

## 8. Intent Router 设计

用户问题可以先路由：

| 意图 | 路由 |
| --- | --- |
| “我多少分能报什么” | `/recommend` |
| “某校某专业近几年怎么样” | `/admissions/trend` |
| “这个专业要求选什么科” | `/subject-requirements` |
| “查一批候选” | `/search/admissions` |
| “今年章程/学费/校区/体检限制” | 官方检索节点 |
| “就业/考研/城市选择” | RAG 知识库 |

Intent Router Prompt：

```text
请判断用户问题属于哪类：
- recommend
- admission_trend
- subject_requirement
- search_admissions
- official_check
- major_career_rag
- clarification

只输出 JSON：
{
  "intent": "",
  "reason": "",
  "missing_fields": []
}

如果缺少分数、位次、科类、再选科目等关键字段，intent=clarification。
```

## 9. 降级策略

如果 API 失败：

- 提示“结构化历史库暂时不可用，不能生成基于位次的可靠推荐”。
- 不输出冲稳保清单。
- 可以只给用户一份信息收集清单。

如果官方检索失败：

- 仍可基于本地历史库输出基础方案。
- 必须提示“最新招生章程、选科、校区、学费、体检限制未完成实时核验”。

如果用户缺少位次：

- 只输出粗略建议。
- 必须要求补充重庆同科类位次。

## 10. 禁止话术

不要说：

- “保证录取”
- “稳录”
- “一定能上”
- “内部数据”
- “官方未发布但我预测”
- “直接照这个填”

推荐说：

- “从 Mock 历史数据看，属于偏冲/偏稳/偏保的参考候选”
- “该结论需要以 2026 招生章程和重庆官方系统复核”
- “由于缺少位次/官方核验，本建议只能作为草案”
