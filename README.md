# 高考志愿填报 Agent 数据服务原型

这是一个面向“重庆新高考志愿填报 Agent”的本地数据底座原型。

核心原则：

- 历史录取数据走 SQLite 结构化库。
- 选科、招生类型、等效位次分档等硬规则由确定性代码处理。
- LLM/Coze 只负责对结果进行解释、归纳和报告生成。
- 当前数据全部是 Mock 数据，仅用于开发测试，不代表真实录取结果。

## 文件结构

```text
db/init.sql              SQLite 建表和 Mock 数据
data/templates/*.csv     真实数据清洗后的标准 CSV 模板
data/samples/*.csv       导入器测试样例
init_db.py               初始化 gaokao_agent.db
import_data.py           CSV 数据校验与导入
gaokao_recommender.py    本地推荐/查询命令行
report_renderer.py       将推荐 JSON 渲染为 Markdown 报告
api_server.py            FastAPI HTTP 服务，供 Coze HTTP 节点调用
verify_recommender.py    推荐层烟测
verify_api.py            API 层烟测
verify_importer.py       数据导入烟测
requirements.txt         API 依赖
```

## 初始化数据库

```powershell
python init_db.py
```

默认会创建或覆盖：

```text
gaokao_agent.db
```

避免覆盖已有数据库：

```powershell
python init_db.py --no-overwrite
```

## 本地命令行推荐

物理类，已选化学，位次 20000 附近，查询计算机方向：

```powershell
python gaokao_recommender.py --score 596 --rank 20000 --subject-type 物理 --second-subjects 化学,生物 --major-interest 计算机
```

物理类，未选化学，查询计算机方向，应触发选科拦截：

```powershell
python gaokao_recommender.py --score 590 --rank 22000 --subject-type 物理 --second-subjects 生物,地理 --major-interest 计算机
```

## 启动 HTTP API

```powershell
python api_server.py
```

默认地址：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## 主要接口

### 健康检查

```http
GET /health
```

### 生成推荐

```http
POST /recommend
Content-Type: application/json
```

请求示例：

```json
{
  "score": 596,
  "rank": 20000,
  "subject_type": "物理",
  "second_subjects": ["化学", "生物"],
  "major_interest": "计算机",
  "risk_level": "均衡",
  "accept_sino_foreign": false
}
```

响应核心字段：

```json
{
  "student_profile": {},
  "warnings": [],
  "candidates": [],
  "excluded": []
}
```

Coze 报告生成节点建议重点使用：

- `warnings`：免责声明和核验提示。
- `candidates`：冲稳保候选、近年分数位次、选科说明、就业方向、风险说明。
- `candidates[].latest_equivalent_min_rank`：按参考年本科线上人数折算后的最低位次，用于冲稳保分档。
- `candidates[].history[].equivalent_min_rank`：每年历史最低位次折算后的等效位次。
- `excluded`：被硬规则过滤的院校专业及原因。

### 生成 Markdown 报告

```http
POST /report
Content-Type: application/json
```

请求体与 `/recommend` 一致。响应包含：

```json
{
  "recommendation": {},
  "markdown_report": "# 重庆高考志愿填报辅助报告\n..."
}
```

如果只需要确定性报告草稿，Coze 可以直接调用 `/report`；如果需要模型润色，则把 `markdown_report` 作为草稿传入最终 LLM 节点。

### 查询院校专业走势

```http
GET /admissions/trend?school_name=重庆邮电大学&major_name=计算机类&subject_type=物理
```

### 查询 2026 选科要求

```http
GET /subject-requirements?school_name=重庆医科大学&major_name=临床医学&requirement_year=2026
```

### 搜索录取历史

```http
GET /search/admissions?subject_type=物理&rank=20000&major_keyword=计算机&accept_sino_foreign=false
```

## Coze 集成建议

工作流节点顺序建议：

1. Start：采集分数、位次、物理/历史、再选科目、专业兴趣、风险偏好、是否接受中外合作。
2. 参数校验：缺位次则提醒降级；缺选科则追问。
3. HTTP 节点：调用本服务 `/recommend`。
4. 官方检索节点：核验 2026 招生章程、选科要求、学费、校区、体检限制。
5. LLM 报告节点：基于 `/recommend` 的 JSON 和官方检索结果生成报告。

报告必须包含：

- 数据来源说明。
- Mock/历史数据不代表最终录取的提醒。
- 官方核验清单。
- 不承诺录取结果。

## 验证

```powershell
python init_db.py
python verify_importer.py
python verify_recommender.py
python verify_api.py
```

期望输出：

```text
All importer smoke tests passed.
All recommender smoke tests passed.
All API smoke tests passed.
```

如果 `verify_api.py` 出现 Starlette/TestClient 的 deprecation warning，但测试通过，可以暂时忽略。

## 下一步

- 按 [docs/data_import.md](D:/我的坚果云/13gaokao/docs/data_import.md) 将 Mock 数据替换为 2021-2025 重庆官方投档表、一分一段表和招生计划。
- 增加波动风险和大小年提示。
- 接入官方实时检索结果缓存。
- 为 Coze 输出完整 System Prompt 和报告模板。
