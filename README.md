# 重启键 Re:Play

> 不是逼你离开游戏，而是帮你重新拿回选择权。

一个面向青少年的游戏行为心理支持比赛原型，采用 **MI（动机式访谈）+ RAG + LLM** 构建可观察、可测试的单页对话系统。

## 当前进度

第四阶段核心能力已经建立，包含：

- 单页面青少年聊天界面；
- ENGAGE、FOCUS、EVOKE、PLAN、REVIEW、SAFETY会话状态；
- 规则风险扫描与语义风险合并；
- OpenAI兼容模型调用与无Key离线降级；
- BM25与中文字符n-gram混合检索；
- 检索分数、命中词和知识来源追踪；
- 匿名SQLite会话持久化；
- 匿名会话自动过期和一键清空；
- 危险生成审核与安全回复替换；
- 六类微行动卡及完成、失败、暂停和复盘；
- 60个可重复比赛对话场景；
- 完整系统与直接建议基线对比；
- 评审面板中的运行诊断、评测证据和本轮决策轨迹；
- 五组虚构比赛演示脚本；
- Docker Compose一键演示环境；
- Pytest、Ruff、前端构建、容器构建和GitHub Actions。

## 设计边界

- 面向青少年本人，不建设家长端或教师端；
- 提供风险识别、心理支持和行为改变辅助，不进行医学诊断；
- 不以游戏时长作为唯一判断依据；
- 不要求立即戒断，强调自主选择和微行动；
- 高风险表达优先进入安全响应；
- 比赛演示只使用虚构数据；
- 不收集真实姓名、学校、住址、手机号或游戏账号；
- 自动评测只衡量工程与对话规则，不代表临床疗效。

## 技术栈

- 前端：React、TypeScript、Vite；
- 后端：Python 3.11+、FastAPI、Pydantic；
- 模型：OpenAI兼容接口，默认`gpt-4o-mini`；
- RAG：BM25 + 中文字符n-gram相似度；
- 数据：匿名SQLite，可切换内存模式；
- 评测：60场景、透明基线、Pytest、Ruff、GitHub Actions；
- 部署：Docker Compose、Nginx反向代理。

## 最快启动：Docker Compose

准备环境变量：

```bash
git clone https://github.com/0401chen/Noname2.0.git
cd Noname2.0
cp .env.example .env
```

在`.env`中填写一种API Key；不填写也能使用离线降级模式。然后执行：

```bash
docker compose up --build
```

访问：

```text
http://localhost:8080
```

后端镜像构建阶段会运行确定性场景评测和透明基线，评测失败会使镜像构建失败。前端通过Nginx将`/api`请求转发到后端。

停止并保留匿名会话卷：

```bash
docker compose down
```

停止并删除匿名会话卷：

```bash
docker compose down -v
```

## 本地开发启动

### 1. 环境变量

程序按以下顺序读取：

```text
LLM_API_KEY → OPENAI_API_KEY → API_KEY
LLM_BASE_URL → OPENAI_BASE_URL → API_BASE
LLM_MODEL → OPENAI_MODEL → gpt-4o-mini
```

兼容配置：

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.vveai.com/v1

API_KEY=
API_BASE=https://api.vveai.com/v1
LLM_MODEL=gpt-4o-mini
```

默认匿名会话配置：

```env
SESSION_STORAGE=sqlite
SESSION_DATABASE_PATH=runtime/replay.sqlite3
SESSION_MAX_MESSAGES=40
SESSION_RETENTION_HOURS=24
SESSION_CLEANUP_INTERVAL_SECONDS=300
```

`SESSION_RETENTION_HOURS`控制匿名会话最长保留时间。需要完全无持久化演示时：

```env
SESSION_STORAGE=memory
```

### 2. 启动后端

```bash
cd backend
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

macOS或Linux：

```bash
source .venv/bin/activate
```

安装并启动：

```bash
python -m pip install -e ".[dev]"
uvicorn noname.main:app --reload --host 0.0.0.0 --port 8000
```

接口文档：`http://localhost:8000/docs`。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问：`http://localhost:5173`。

## 比赛演示模式

页面中的“比赛演示场景”提供五组虚构脚本：

1. 熬夜与队友关系；
2. 最后一局循环；
3. 学习压力与逃避循环；
4. 父母控制与自主需要；
5. 高风险安全路由。

载入场景后会自动开启评审模式，但不会自动发送消息。演示者可以按顺序点击“第1句”“第2句”“第3句”，也可以修改文本后发送。高风险脚本有单独的视觉提示。

## 后端接口

| 接口 | 作用 |
|---|---|
| `GET /api/health` | 最小健康检查 |
| `GET /api/diagnostics` | 不包含密钥的运行诊断 |
| `GET /api/demo/scenarios` | 获取虚构演示脚本 |
| `GET /api/evaluation/summary` | 获取评测和基线摘要 |
| `POST /api/chat` | 进行会话 |
| `DELETE /api/sessions/{session_id}` | 删除匿名会话 |

运行诊断只展示版本、模型模式、接口主机名、存储类型、会话保留时间、知识条目数和评测准备状态，不返回API Key。

## 测试与评测

### 后端测试

```bash
cd backend
ruff check .
pytest -q
```

### 60个确定性对话场景

```bash
cd backend
python -m noname.evaluation
```

读取：

```text
evaluation/scenarios/core.json
evaluation/scenarios/extended.json
```

生成：

```text
evaluation/results/latest.json
```

### 透明基线对比

```bash
cd backend
python -m noname.benchmark
```

生成：

```text
evaluation/results/benchmark.json
```

朴素基线是一个公开、可审查的直接建议流程，仅用于工程对照，不代表所有通用大模型表现。

### 在线模型评测

```bash
cd backend
python -m noname.evaluation --online
python -m noname.benchmark --online-full --online-baseline
```

在线结果受模型版本、供应商、网络和采样随机性影响，不能替代人工安全复核。

### 前端构建

```bash
cd frontend
npm run build
```

## 评审模式证据

系统级证据：

- 运行版本和模型模式；
- 模型接口主机名，不显示密钥；
- 会话存储和自动清理时长；
- 知识条目数量；
- 60场景通过情况；
- 高风险路由率；
- 行动卡形成率；
- 平均处理耗时；
- 完整系统与直接建议基线差异。

每轮会话证据：

- 会话阶段；
- 风险等级和触发信号；
- 当前关注问题；
- 心理需要；
- 改变语言与维持现状语言；
- MI策略；
- RAG命中和检索方法；
- BM25、n-gram分数和命中词；
- 知识来源；
- 回复质量标记；
- LLM、离线降级或安全模板；
- 本轮处理耗时。

只有运行评测后，页面才展示真实生成的评测汇总；仓库不预置伪造分数。

## 推荐答辩演示

1. 使用`docker compose up --build`启动；
2. 在单页中选择“熬夜与队友关系”；
3. 依次发送三句虚构脚本；
4. 展示睡眠关注、归属需要、MI策略、RAG证据和行动卡；
5. 发送一次复盘表达，展示行动状态更新；
6. 重置并载入“高风险安全路由”；
7. 展示普通游戏建议被停止、会话切换到SAFETY；
8. 在评审面板展示运行诊断、60场景和基线证据。

## 仓库结构

```text
backend/
  src/noname/          会话、安全、RAG、存储、评测、基线、诊断与API
  tests/               单元、集成和业务编排测试
frontend/
  src/                 青少年视图、虚构演示和评审视图
docs/
  product.md           产品需求
  architecture.md      系统架构
  safety.md            安全和伦理规范
  evaluation.md        评测方法
  acceptance.md        验收标准
knowledge/reviewed/    经审核知识条目
evaluation/scenarios/  60个可重复对话场景
evaluation/results/    本地、容器或CI生成的评测结果
```

## 安全说明

本项目不能替代心理咨询、医疗诊断或紧急救援。不要提交真实未成年人对话、姓名、学校、地址、账号或其他敏感信息，也不要将任何API密钥提交到GitHub。
