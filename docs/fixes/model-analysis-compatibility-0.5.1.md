# 0.5.1 在线分析兼容修复

## 现象

OpenAI兼容供应商能够正常返回HTTP 200和JSON，但可能使用 `current_emotions`、`current_emotion`、`mi_stage`、`retrieval_needed`、`risk_level` 等语义等价字段，并省略必填的 `summary`。旧版本会因此让整轮语义分析回退到启发式分析。

## 修复

- 在提示词中加入精确输出字段契约；
- 新增供应商分析字段适配层；
- 缺少 `summary` 等字段时继承确定性规则分析结果；
- 支持常见情绪、阶段、心理需要、动机、风险和检索字段别名；
- 过滤未知枚举，避免供应商自由命名破坏会话状态；
- 保留风险合并规则，模型不能降低规则层风险；
- 增加适配层单元测试和LLM客户端接入测试。

## 本地验证

更新并重启后端后发送普通演示消息。兼容修复生效时，日志可能出现：

```text
INFO noname.llm Normalized provider analysis fields: ...
```

这表示供应商JSON经过安全字段适配后已被语义分析层采用，不是离线降级。日志中不应再反复出现：

```text
LLM analysis failed: ... summary Field required
```
