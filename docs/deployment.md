# 部署说明

Coze 的 HTTP 节点通常需要访问公网 URL。`http://127.0.0.1:8000` 只适合本机开发，不能直接被 Coze 云端调用。

## 本地启动

```powershell
python init_db.py
python api_server.py
```

访问：

```text
http://127.0.0.1:8000/docs
```

## Docker 启动

构建镜像：

```powershell
docker build -t gk-volunteer-agent .
```

运行容器：

```powershell
docker run --rm -p 8000:8000 gk-volunteer-agent
```

访问：

```text
http://127.0.0.1:8000/health
```

## Docker Compose

```powershell
docker compose up --build
```

停止：

```powershell
docker compose down
```

## 给 Coze 调用

建议部署到可被公网访问的环境，例如：

- 云服务器 + Docker
- Render / Railway / Fly.io 等容器平台
- 临时测试用 ngrok / cloudflared 隧道

Coze HTTP 节点配置示例：

```text
Method: POST
URL: https://your-domain.example.com/recommend
Headers:
  Content-Type: application/json
```

如果直接要报告草稿：

```text
URL: https://your-domain.example.com/report
```

## 生产注意事项

- 当前数据库默认由 `init_db.py` 从 Mock SQL 初始化，真实部署前应导入官方清洗后的 CSV。
- 不要把本地生成的 `gaokao_agent.db` 提交到 Git。
- 公网部署时建议加网关鉴权、请求限流和访问日志。
- 正式志愿填报前必须核验重庆市教育考试院、重庆招考信息网、阳光高考和高校招生章程。
