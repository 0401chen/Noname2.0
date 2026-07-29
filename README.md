# Noname助手 Re:Play

> 不是逼你离开游戏，而是帮你重新拿回选择权。

面向青少年的游戏行为心理支持比赛原型，采用 **MI（动机式访谈）+ RAG + LLM** 构建可观察、可测试的单页对话系统。

## 当前版本

第五阶段 `0.5.0` 已包含：

- 单页面青少年对话和比赛演示场景；
- ENGAGE、FOCUS、EVOKE、PLAN、REVIEW、SAFETY会话状态；
- 规则风险扫描、模型语义分析和风险只升不降；
- OpenAI兼容接口、JSON模式兼容降级和无Key离线回复；
- 模型接口独立自检命令；
- 0—10分改变意愿输入和短文本上下文继承；
- BM25与中文字符n-gram混合检索；
- 匿名SQLite会话、自动过期和一键清空；
- 危险生成、欺骗建议、内部提示泄露和过长回复审核；
- 六类微行动卡及完成、失败、暂停和复盘；
- 60个确定性比赛场景和透明基线；
- 评审面板中的运行诊断、评测证据和本轮决策轨迹；
- Pytest、Ruff、前端构建、Docker Compose和GitHub Actions。

## 产品边界

- 面向青少年本人，不建设家长端或教师端；
- 提供风险识别、心理支持和行为改变辅助，不进行医学诊断；
- 不以游戏时长作为唯一判断依据；
- 不要求立即戒断，强调自主选择和微行动；
- 高风险表达优先进入安全响应；
- 比赛演示只使用虚构数据；
- 不收集真实姓名、学校、住址、手机号或游戏账号；
- 自动评测只衡量工程与对话规则，不代表临床疗效。

## Windows本地启动（推荐开发方式）

### 1. 下载代码并准备配置

```powershell
cd D:\
git clone https://github.com/0401chen/Noname2.0.git
cd D:\Noname2.0
Copy-Item .env.example .env
notepad .env
```

填写：

```env
LLM_API_KEY=你的API密钥
LLM_BASE_URL=https://api.vveai.com/v1
LLM_MODEL=gpt-4o-mini
VITE_AGENT_NAME=Noname助手
```

不要把`.env`、API Key或真实未成年人对话提交到GitHub。

### 2. 创建Conda环境并安装后端

```powershell
conda create -n noname2 python=3.11 -y
conda activate noname2
cd D:\Noname2.0
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

### 3. 检查模型接口

后端安装完成后运行：

```powershell
cd D:\Noname2.0\backend
python -m noname.provider_check
```

成功时会显示：

- 模型名称；
- 接口主机名；
- 使用`json-mode`还是兼容的`prompt-json`；
- 单次测试耗时。

该命令不会输出API Key。接口不支持`response_format`或`temperature`时，客户端会自动改用兼容调用方式。

### 4. 安装Node.js和前端依赖

```powershell
conda activate noname2
conda install -c conda-forge nodejs=22 -y
cd D:\Noname2.0\frontend
npm install
```

### 5. 启动后端

第一个PowerShell终端：

```powershell
conda activate noname2
cd D:\Noname2.0\backend
uvicorn noname.main:app --reload --host 127.0.0.1 --port 8000
```

检查：

```text
http://127.0.0.1:8000/api/health
http://127.0.0.1:8000/docs
```

### 6. 启动前端

第二个PowerShell终端：

```powershell
conda activate noname2
cd D:\Noname2.0\frontend
npm run dev
```

访问：

```text
http://localhost:5173
```

## 后续更新代码

停止前后端后，在项目根目录运行：

```powershell
cd D:\Noname2.0
git pull
```

只有依赖文件发生变化时才需要重新执行：

```powershell
python -m pip install -r requirements-dev.txt
cd frontend
npm install
```

普通代码更新只需重新启动前端和后端。

## Docker统一部署（最终阶段）

Docker不是本地开发的必要条件。最终需要一键部署时：

```powershell
cd D:\Noname2.0
docker compose up --build
```

访问：

```text
http://localhost:8080
```

停止并保留匿名会话卷：

```powershell
docker compose down
```

停止并删除匿名会话卷：

```powershell
docker compose down -v
```

## 环境变量

读取顺序：

```text
LLM_API_KEY → OPENAI_API_KEY → API_KEY
LLM_BASE_URL → OPENAI_BASE_URL → API_BASE
LLM_MODEL → OPENAI_MODEL → gpt-4o-mini
```

默认匿名会话配置：

```env
SESSION_STORAGE=sqlite
SESSION_DATABASE_PATH=runtime/replay.sqlite3
SESSION_MAX_MESSAGES=40
SESSION_RETENTION_HOURS=24
SESSION_CLEANUP_INTERVAL_SECONDS=300
```

完全无持久化演示：

```env
SESSION_STORAGE=memory
```

## 比赛演示模式

页面提供五组虚构脚本：

1. 熬夜与队友关系；
2. 最后一局循环；
3. 学习压力与逃避循环；
4. 父母控制与自主需要；
5. 高风险安全路由。

载入场景后会开启评审模式，但不会自动发送消息。演示者可逐句发送或修改文字。高风险脚本有单独视觉提示。

## 后端接口

| 接口 | 作用 |
|---|---|
| `GET /api/health` | 最小健康检查 |
| `GET /api/diagnostics` | 不包含密钥的运行诊断 |
| `GET /api/demo/scenarios` | 获取虚构演示脚本 |
| `GET /api/evaluation/summary` | 获取评测和基线摘要 |
| `POST /api/chat` | 进行会话 |
| `DELETE /api/sessions/{session_id}` | 删除匿名会话 |

## 测试与评测

后端测试：

```powershell
cd D:\Noname2.0\backend
ruff check .
pytest -q
```

60个确定性场景：

```powershell
python -m noname.evaluation
```

透明基线：

```powershell
python -m noname.benchmark
```

在线模型评测：

```powershell
python -m noname.evaluation --online
python -m noname.benchmark --online-full --online-baseline
```

前端生产构建：

```powershell
cd D:\Noname2.0\frontend
npm run build
```

在线结果受模型版本、供应商、网络和采样随机性影响，不能替代人工安全复核。

## 推荐答辩演示

1. 先运行模型接口自检、60场景和透明基线；
2. 启动前后端并选择“熬夜与队友关系”；
3. 依次发送虚构脚本，展示睡眠关注、归属需要和MI策略；
4. 形成三天行动卡并发送一次复盘表达；
5. 重置后载入“高风险安全路由”；
6. 展示普通游戏建议停止、会话进入SAFETY；
7. 在评审面板展示运行诊断、RAG证据、评测和基线差异。

## 安全说明

本项目不能替代心理咨询、医疗诊断或紧急救援。不要提交真实未成年人对话、姓名、学校、地址、账号或其他敏感信息，也不要将任何API密钥提交到GitHub。
