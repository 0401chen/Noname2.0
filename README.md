# 重启键 Re:Play

> 不是逼你离开游戏，而是帮你重新拿回选择权。

一个面向青少年的游戏行为心理支持比赛原型，采用 **MI（动机式访谈）+ RAG + LLM** 构建可观察、可测试的单页对话系统。

## 当前进度

第一版可运行骨架已经建立，包含：

- 单页面青少年聊天界面；
- 可切换的评审可解释视图；
- ENGAGE、FOCUS、EVOKE、PLAN、REVIEW、SAFETY 会话状态；
- 规则风险扫描与语义风险合并；
- OpenAI 兼容模型调用；
- 无 API Key 时的确定性降级流程；
- 本地审核知识检索；
- 回复质量检查；
- 三天微行动卡；
- Pytest 与 GitHub Actions；
- 第一批端到端评测场景。

## 设计边界

- 面向青少年本人，不建设家长端或教师端；
- 进行风险识别、心理支持和行为改变辅助，不进行医学诊断；
- 不以游戏时长作为唯一判断依据；
- 不要求用户立即戒断游戏，强调自主选择和微行动；
- 高风险表达会优先进入安全响应流程；
- 比赛演示只使用虚构数据。

## 技术栈

- 前端：React + TypeScript + Vite；
- 后端：Python 3.11+、FastAPI、Pydantic；
- 模型：OpenAI 兼容接口，默认 `gpt-4o-mini`；
- RAG：第一阶段采用透明本地词法检索；
- 数据：第一阶段使用匿名内存会话；
- 测试：Pytest、Ruff、GitHub Actions。

## 快速启动

### 1. 获取项目并准备环境变量

```bash
git clone https://github.com/0401chen/Noname2.0.git
cd Noname2.0
cp .env.example .env
```

在 `.env` 中填写一种 API Key 即可。程序按以下顺序读取：

```text
LLM_API_KEY → OPENAI_API_KEY → API_KEY
LLM_BASE_URL → OPENAI_BASE_URL → API_BASE
LLM_MODEL → OPENAI_MODEL → gpt-4o-mini
```

当前兼容配置：

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.vveai.com/v1

API_KEY=
API_BASE=https://api.vveai.com/v1
LLM_MODEL=gpt-4o-mini
```

不填写 API Key 也能启动，系统会进入可测试的离线降级模式。

### 2. 启动后端

```bash
cd backend
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

macOS 或 Linux：

```bash
source .venv/bin/activate
```

安装并启动：

```bash
python -m pip install -e ".[dev]"
uvicorn noname.main:app --reload --host 0.0.0.0 --port 8000
```

后端接口文档位于 `http://localhost:8000/docs`。

### 3. 启动前端

打开另一个终端：

```bash
cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`。

## 测试

后端：

```bash
cd backend
ruff check .
pytest -q
```

前端：

```bash
cd frontend
npm run build
```

## 推荐演示流程

1. 开启评审模式；
2. 输入：“我每天打到两点，但我觉得没什么，反正学习也学不好”；
3. 输入：“主要是第二天很困，但我不能提前下，队友都在”；
4. 选择：“可以试三天”；
5. 输入：“可以试三天提前20分钟”，生成行动卡；
6. 重置会话；
7. 输入：“反正活着没意思，游戏关了更没意思”，展示安全响应。

## 仓库结构

```text
backend/
  src/noname/          会话、安全、RAG、LLM 与 API
  tests/               单元和业务编排测试
frontend/
  src/                 单页青少年视图与评审视图
docs/
  architecture.md      系统架构
  safety.md            安全和伦理规范
  acceptance.md        第一阶段验收标准
knowledge/reviewed/    经审核知识条目
evaluation/scenarios/  端到端对话场景
```

## 安全说明

本项目不能替代心理咨询、医疗诊断或紧急救援。不要提交真实未成年人对话、姓名、学校、地址、账号或其他敏感信息，也不要将任何 API 密钥提交到 GitHub。
