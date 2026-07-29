# Agent 品牌配置

## 当前名称

面向用户展示的 Agent 名称统一为：

```text
Noname助手
```

内部 Python 包名、仓库名、数据库文件名和评测命令不随品牌名称改变，避免影响运行和历史兼容。

## 本地开发

根目录 `.env` 中保留：

```env
VITE_AGENT_NAME=Noname助手
```

修改该值后，需要停止并重新运行前端：

```powershell
cd frontend
npm run dev
```

## Docker 部署

部署前确认根目录 `.env` 中存在：

```env
VITE_AGENT_NAME=Noname助手
```

然后重新构建前端镜像：

```powershell
docker compose up --build
```

Agent 名称属于 Vite 构建期配置，因此仅重启旧容器不会更新名称，必须重新执行构建。

## 部署验收

上线或比赛演示前检查：

1. 页面左上角显示“Noname助手”；
2. 助手消息署名显示“Noname助手”；
3. 浏览器标签显示“Noname助手 Re:Play”；
4. `/docs` 的 API 标题显示“Noname助手 Re:Play API”；
5. 页面中不再出现旧名称“重启键”。
