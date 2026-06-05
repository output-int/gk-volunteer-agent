# 高考志愿填报 Agent 数据服务原型

这是一个面向“重庆新高考志愿填报 Agent”的本地数据底座原型。

核心原则：

- 历史录取数据走 SQLite 结构化库。
- 选科、招生类型、等效位次分档等硬规则由确定性代码处理。
- Markdown 报告由确定性 Python 模块生成，后续可按需要再接入其他展示层。
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
api_server.py            FastAPI HTTP 服务
verify_recommender.py    推荐层烟测
verify_api.py            API 层烟测
verify_importer.py       数据导入烟测
run_checks.py            本地/CI 统一检查入口
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

也可以显式使用 uvicorn：

```powershell
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
```

默认地址：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

本地网页：

```text
http://127.0.0.1:8000/
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

结构化推荐结果建议重点查看：

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

如果只需要本地确定性报告草稿，直接调用 `/report` 并读取 `markdown_report`。

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

## 本地 API 快速测试

启动服务后，另开一个终端运行：

查看冲稳保结构化结果：

```powershell
python -c "import json, urllib.request; data={'score':596,'rank':20000,'subject_type':'物理','second_subjects':['化学','生物'],'major_interest':'计算机','risk_level':'均衡','accept_sino_foreign':False}; req=urllib.request.Request('http://127.0.0.1:8000/recommend', data=json.dumps(data).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST'); print(json.dumps(json.load(urllib.request.urlopen(req)), ensure_ascii=False, indent=2))"
```

查看 Markdown 报告：

```powershell
python -c "import json, urllib.request; data={'score':596,'rank':20000,'subject_type':'物理','second_subjects':['化学','生物'],'major_interest':'计算机','risk_level':'均衡','accept_sino_foreign':False}; req=urllib.request.Request('http://127.0.0.1:8000/report', data=json.dumps(data).encode('utf-8'), headers={'Content-Type':'application/json'}, method='POST'); print(json.load(urllib.request.urlopen(req))['markdown_report'])"
```

## 验证

推荐直接运行：

```powershell
python run_checks.py
```

它会依次执行数据库初始化、导入器烟测、推荐层烟测、API 烟测、报告渲染和示例文件解析。

也可以手动分步运行：

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
- 增加本地前端页面或命令行交互入口。
