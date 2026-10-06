# Noname助手

> 不是逼你离开游戏，而是帮你重新拿回选择权。

Noname助手是一个面向 12—18 岁青少年的游戏行为智能支持比赛原型。系统不以“戒游戏”或单纯限制时长为目标，而是通过动机式访谈（MI）风格的多轮会话，帮助用户理解游戏带来的价值与现实影响，在用户愿意改变时，把其自己的想法整理成足够小、可执行、可调整的微行动实验；当出现高风险表达时，系统会暂停普通游戏建议并切换到持续的安全优先模式。

当前 `Final-version` 的核心能力包括：

- MI 驱动的状态化多轮会话：`ENGAGE / FOCUS / EVOKE / PLAN / REVIEW / SAFETY`；
- 当前话题 `focus` 与持久主线 `anchor` 分离，减少多轮对话跑偏；
- 最近原始消息 + 滚动摘要 + 结构化状态组成长期会话记忆；
- 本地 `BM25 + 中文字符 n-gram` 混合 RAG，并保留可追溯的检索分数和来源；
- 基于用户行动意图的结构化微行动实验，而不是通用自主 Planner；
- 规则风险检测 + LLM 上下文理解 + 持久 SafetyConversationState 的多层安全架构；
- 生成后质量审核和确定性 fallback；
- 先完成完整生成与安全审核、再向前端分段发送的应用层流式输出；
- `TURN_STATE / SAFETY_STATE / LONG_MEMORY` 结构化开发日志；
- 自动化测试、确定性场景评测和透明基线对比框架。

## 1. 项目定位

Noname助手的目标不是诊断“游戏成瘾”，也不是替家长或学校强制管理青少年，而是提供一个相对中立的支持空间，帮助用户回答三个问题：

1. 游戏对我为什么重要？
2. 它最近有没有带来我不喜欢的影响？
3. 如果我想改变，哪个最小步骤是我自己愿意尝试的？

系统同时设置独立安全层。当出现明确自伤、自杀、无法保证当前安全、暴力/虐待等高风险信息时，普通会话流程暂停，优先确认安全并鼓励连接现实中的可信任支持。

## 2. 技术路线

```text
用户输入
   ↓
规则风险扫描
   ↓
确定性会话初步分析
   ↓
LLM结构化会话分析
   ↓
MI阶段 + 当前focus + 主线anchor
   ↓
策略选择
   ↓
按需RAG / 长期会话记忆
   ↓
回复生成
   ↓
质量审核 / 安全校验
   ↓
微行动计划与会话状态更新
   ↓
应用层流式返回前端
```

高风险时，流程切换到独立的 SAFETY 状态机，不继续普通游戏建议。

详细说明见：

- `docs/product.md`
- `docs/architecture.md`
- `docs/safety.md`
- `docs/evaluation.md`
- `docs/acceptance.md`

## 3. 技术栈

### 前端

- React
- TypeScript
- Vite
- Lucide React

### 后端

- Python 3.11
- FastAPI
- Pydantic
- OpenAI 兼容接口
- 本地知识库
- Pytest

## 4. 本地运行

### 后端

```powershell
conda activate noname2
cd D:\Noname2.0\backend
uvicorn noname.main:app --reload --host 127.0.0.1 --port 8000
```

### 前端

```powershell
conda activate noname2
cd D:\Noname2.0\frontend
npm run dev
```

打开：

```text
http://localhost:5173
```

## 5. 会话模块

普通会话阶段：

```text
ENGAGE  建立关系，理解游戏价值
FOCUS   明确用户最想处理的问题
EVOKE   引出用户自己的改变理由
PLAN    形成微行动实验
REVIEW  根据后续反馈复盘调整
```

高风险阶段：

```text
SAFETY  暂停普通流程，优先处理当前安全
```

系统不会只依赖当前一句话。`SessionState` 还保存：

- `primary_focus_topic`
- `primary_focus_excerpt`
- `conversation_summary`
- `action_plan`
- `safety_state`

因此可以在探索朋友、团队合作、成就感等支线时，仍保留用户最初提出的主线困扰。

## 6. RAG

当前知识检索采用本地透明混合方案：

```text
BM25
+
中文字符 n-gram 相似度
+
关键词加权
+
类别加权
```

RAG 只在需要时触发。高风险状态下仅允许检索安全类别知识。

## 7. 微行动实验

当用户明确表达愿意尝试，或直接提出可执行行为时，系统可以形成结构化 `ActionPlan`，例如：

- 每天少玩一定时间；
- 设置结束时间；
- 提前结束；
- 设置提醒；
- 每局结束后先暂停几分钟再决定是否继续。

计划可以包含：行为、持续时间、原因、障碍和应对方式。行为优先来自用户自己的表达；部分字段在信息不足时由系统根据当前会话辅助补全，因此该模块应准确描述为“用户意图驱动的结构化微行动规划”，而不是通用自主任务规划器。

## 8. 安全

安全层包含：

1. 确定性规则风险扫描；
2. LLM 安全上下文理解；
3. 会话级持续 SafetyConversationState；
4. 程序化安全退出条件；
5. 安全回复生成与确定性兜底。

模型不能降低规则层已识别的风险，也不能自行决定退出 SAFETY。

## 9. 长期会话记忆

系统使用：

```text
近期原始消息
+
较早对话滚动摘要
+
主线锚点 / 行动计划 / 安全状态等结构化状态
```

当前长对话达到压缩阈值后，会把较早消息摘要化并保留最近 16 条消息。

## 10. 流式输出

前端使用 `/api/chat/stream`。

当前实现不是未经审核的模型 token 直出，而是：

```text
完整生成
→ 风险与质量审核
→ start
→ meta
→ delta...
→ done
```

这样优先保证安全和最终回复一致性。

## 11. 测试与评测

核心测试：

```powershell
cd D:\Noname2.0\backend
pytest -q `
  tests/test_final_version.py `
  tests/test_service.py `
  tests/test_safety.py `
  tests/test_evaluation.py
```

前端生产构建：

```powershell
cd D:\Noname2.0\frontend
npm run build
```

确定性场景评测：

```bash
cd backend
python -m noname.evaluation
```

透明基线：

```bash
python -m noname.benchmark
```

测试和场景结果验证的是工程流程与预设对话行为，不应解释为临床疗效。

## 12. 当前边界

当前项目是比赛原型，不宣称：

- 能够医学诊断游戏障碍；
- 能够替代心理治疗或现实危机支持；
- 已经证明能降低青少年游戏问题发生率；
- 已完成大规模真实未成年人研究；
- 具备通用复杂任务自主规划能力。

后续若进入真实用户研究，应进一步完成伦理审查、未成年人数据治理、安全误报/漏报评估和人工效果评测。
