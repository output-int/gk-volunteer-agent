# OpenAPI / Coze 导入说明

仓库提供一份由 FastAPI 自动导出的 OpenAPI 规格：

```text
openapi/openapi.json
```

生成命令：

```powershell
python export_openapi.py --check
```

`--check` 会确认核心路径存在：

- `/health`
- `/recommend`
- `/report`
- `/admissions/trend`
- `/subject-requirements`
- `/search/admissions`

## Coze 导入思路

1. 先把 API 服务部署到 Coze 可访问的公网地址。
2. 运行 `python export_openapi.py --check`，确认 `openapi/openapi.json` 是最新的。
3. 在 Coze 插件/工具配置中导入 OpenAPI 规格。
4. 将工具配置 URL 替换成真实公网域名。
5. 优先使用 `/recommend` 获取结构化候选，或使用 `/report` 获取确定性 Markdown 报告草稿。

## 推荐工作流

简单版：

```text
Start -> /report -> 返回 markdown_report
```

增强版：

```text
Start -> /recommend -> 官方检索 -> LLM 报告润色
```

增强版更适合正式填报前使用，因为它可以补充最新招生章程、学费、校区、体检限制等核验信息。

## 维护要求

如果修改了 `api_server.py` 的接口：

```powershell
python export_openapi.py --check
python run_checks.py
```

并提交更新后的：

```text
openapi/openapi.json
```
