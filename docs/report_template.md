# 报告模板说明

`report_renderer.py` 提供一个确定性的 Markdown 报告生成器。它只使用推荐 API 返回的 JSON 和可选官方核验 JSON，不调用 LLM，也不会创造新事实。

## 命令行用法

```powershell
python report_renderer.py --recommendation-json examples/recommend_response.json --output examples/recommend_report.md
```

如果已经有官方核验结果：

```powershell
python report_renderer.py --recommendation-json examples/recommend_response.json --official-checks-json examples/official_checks_sample.json --output examples/recommend_report.md
```

## API 用法

启动服务：

```powershell
python api_server.py
```

调用：

```http
POST /report
Content-Type: application/json
```

请求体与 `/recommend` 一致。

## 输出结构

报告固定包含：

- 考生画像
- 核心结论
- 冲稳保候选
- 被过滤项目
- 官方核验清单
- 下一步行动
- 风险声明

## Coze 建议

两种接法都可以：

1. 直接调用 `/report`，把 `markdown_report` 返回给用户。
2. 调用 `/recommend`，再用 Coze 的 LLM 节点按 `docs/coze_workflow.md` 的报告 Prompt 润色。

如果走 LLM 润色，必须要求模型保留：

- 位次、等效位次、最低分等硬事实。
- 被过滤项目和原因。
- 风险声明。
- 官方核验清单。
