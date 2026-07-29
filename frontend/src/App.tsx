import {
  AlertTriangle,
  Bot,
  BrainCircuit,
  CheckCircle2,
  CircleHelp,
  Gamepad2,
  Loader2,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import type {
  ActionPlan,
  ChatResponse,
  Message,
  ReviewerTrace,
} from "./types";

const starterReplies = [
  "最近总是玩到很晚",
  "我想少玩，但停不下来",
  "父母根本不理解我",
  "游戏只是让我放松",
];

const stageLabels: Record<string, string> = {
  ENGAGE: "建立关系",
  FOCUS: "确定重点",
  EVOKE: "唤起动机",
  PLAN: "形成计划",
  REVIEW: "复盘调整",
  SAFETY: "安全响应",
};

const focusLabels: Record<string, string> = {
  sleep: "睡眠",
  stopping: "停止困难",
  school: "学习与拖延",
  family: "家庭冲突",
  emotion: "情绪压力",
  social: "队友与社交",
};

const needLabels: Record<string, string> = {
  belonging: "归属感",
  achievement: "成就感",
  autonomy: "自主感",
  relaxation: "放松",
  escape: "暂时逃离压力",
  connection: "连接与被需要",
};

function createId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`;
}

const initialMessage: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "嗨，我不会一上来就让你戒游戏。我们可以先弄清楚，游戏对你意味着什么，以及它最近有没有带来一些你不喜欢的影响。你现在更想聊哪件事？",
};

function App() {
  const [sessionId, setSessionId] = useState(createId);
  const [messages, setMessages] = useState<Message[]>([initialMessage]);
  const [input, setInput] = useState("");
  const [quickReplies, setQuickReplies] = useState(starterReplies);
  const [actionPlan, setActionPlan] = useState<ActionPlan | null>(null);
  const [trace, setTrace] = useState<ReviewerTrace | null>(null);
  const [reviewerMode, setReviewerMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ageGroup, setAgeGroup] = useState("15-16");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const balanceItems = useMemo(() => {
    const items: string[] = [];
    if (trace?.focus_topic) {
      items.push(focusLabels[trace.focus_topic] ?? trace.focus_topic);
    }
    for (const need of trace?.psychological_needs ?? []) {
      const label = needLabels[need.name] ?? need.name;
      if (!items.includes(label)) items.push(label);
    }
    return items.slice(0, 4);
  }, [trace]);

  async function sendMessage(rawText: string) {
    const text = rawText.trim();
    if (!text || loading) return;

    const userMessage: Message = { id: createId(), role: "user", content: text };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setQuickReplies([]);
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
          age_group: ageGroup,
          reviewer_mode: reviewerMode,
        }),
      });

      if (!response.ok) {
        throw new Error("服务暂时没有响应");
      }

      const data = (await response.json()) as ChatResponse;
      setMessages((current) => [
        ...current,
        { id: createId(), role: "assistant", content: data.reply },
      ]);
      setQuickReplies(data.quick_replies);
      setActionPlan(data.action_plan);
      setTrace(data.trace);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "发送失败");
      setQuickReplies(["重新发送", "先缓一缓"]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  async function resetSession() {
    try {
      await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
    } finally {
      setSessionId(createId());
      setMessages([initialMessage]);
      setQuickReplies(starterReplies);
      setActionPlan(null);
      setTrace(null);
      setError(null);
      setInput("");
    }
  }

  function toggleReviewerMode() {
    setReviewerMode((current) => !current);
    setTrace(null);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-icon" aria-hidden="true">
            <Gamepad2 size={24} />
          </div>
          <div>
            <div className="brand-line">
              <h1>重启键</h1>
              <span>Re:Play</span>
            </div>
            <p>不是逼你离开游戏，而是帮你重新拿回选择权。</p>
          </div>
        </div>

        <div className="top-actions">
          <label className="age-select">
            <span>年龄段</span>
            <select value={ageGroup} onChange={(event) => setAgeGroup(event.target.value)}>
              <option value="12-14">12—14岁</option>
              <option value="15-16">15—16岁</option>
              <option value="17-18">17—18岁</option>
              <option value="unspecified">不想填写</option>
            </select>
          </label>

          <button
            className={`review-toggle ${reviewerMode ? "active" : ""}`}
            type="button"
            onClick={toggleReviewerMode}
          >
            <BrainCircuit size={17} />
            {reviewerMode ? "评审模式已开" : "评审模式"}
          </button>

          <button className="icon-button" type="button" onClick={() => void resetSession()}>
            <RefreshCw size={18} />
            <span>重置</span>
          </button>
        </div>
      </header>

      <div className="prototype-notice">
        <ShieldCheck size={16} />
        <span>比赛原型：提供心理支持与风险识别，不进行医学诊断，也不能替代专业帮助。</span>
        <button
          type="button"
          onClick={() => void sendMessage("我现在感觉很危险，需要马上获得帮助")}
        >
          我现在需要帮助
        </button>
      </div>

      <main className="main-layout">
        <section className="chat-panel" aria-label="对话区">
          <div className="chat-heading">
            <div>
              <span className="eyebrow">匿名对话</span>
              <h2>先从你最在意的事情开始</h2>
            </div>
            <div className="privacy-chip">
              <ShieldCheck size={15} />
              不需要真实姓名或学校
            </div>
          </div>

          <div className="messages" aria-live="polite">
            {messages.map((message) => (
              <article key={message.id} className={`message ${message.role}`}>
                <div className="avatar" aria-hidden="true">
                  {message.role === "assistant" ? <Bot size={19} /> : <UserRound size={19} />}
                </div>
                <div className="message-body">
                  <span>{message.role === "assistant" ? "重启键" : "我"}</span>
                  <p>{message.content}</p>
                </div>
              </article>
            ))}

            {loading && (
              <article className="message assistant">
                <div className="avatar" aria-hidden="true">
                  <Bot size={19} />
                </div>
                <div className="message-body loading-message">
                  <span>重启键</span>
                  <p>
                    <Loader2 className="spin" size={17} />
                    正在理解你刚才说的重点……
                  </p>
                </div>
              </article>
            )}
            <div ref={bottomRef} />
          </div>

          {quickReplies.length > 0 && (
            <div className="quick-replies" aria-label="快捷回复">
              {quickReplies.map((reply) => (
                <button key={reply} type="button" onClick={() => void sendMessage(reply)}>
                  {reply}
                </button>
              ))}
            </div>
          )}

          {error && (
            <div className="error-banner">
              <AlertTriangle size={17} />
              {error}。你的文字还保留在页面上，可以稍后重试。
            </div>
          )}

          <form className="composer" onSubmit={handleSubmit}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage(input);
                }
              }}
              placeholder="可以说说最近一次玩到停不下来的情况……"
              maxLength={3000}
              disabled={loading}
            />
            <div className="composer-footer">
              <span>决定权始终在你。按 Enter 发送，Shift + Enter 换行。</span>
              <button type="submit" disabled={!input.trim() || loading}>
                <Send size={17} />
                发送
              </button>
            </div>
          </form>
        </section>

        <aside className="side-panel" aria-label="平衡地图与评审信息">
          <section className="side-card balance-card">
            <div className="card-title">
              <div>
                <span className="eyebrow">我的平衡地图</span>
                <h3>目前对话中的重点</h3>
              </div>
              <Sparkles size={19} />
            </div>

            {balanceItems.length > 0 ? (
              <div className="tag-list">
                {balanceItems.map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            ) : (
              <p className="empty-copy">聊几句后，这里会出现由你确认的关注点，而不是给你贴标签。</p>
            )}

            <div className="balance-note">
              <CircleHelp size={16} />
              系统关注游戏带来的价值和影响，不只统计游戏时长。
            </div>
          </section>

          <section className="side-card plan-card">
            <div className="card-title">
              <div>
                <span className="eyebrow">我的实验</span>
                <h3>{actionPlan?.title ?? "还没有制定行动"}</h3>
              </div>
              {actionPlan ? <CheckCircle2 size={20} /> : <Gamepad2 size={20} />}
            </div>

            {actionPlan ? (
              <dl className="plan-grid">
                <div>
                  <dt>我要尝试</dt>
                  <dd>{actionPlan.behavior}</dd>
                </div>
                <div>
                  <dt>持续时间</dt>
                  <dd>{actionPlan.duration}</dd>
                </div>
                <div>
                  <dt>我的原因</dt>
                  <dd>{actionPlan.reason}</dd>
                </div>
                <div>
                  <dt>把握程度</dt>
                  <dd>{actionPlan.confidence}/10</dd>
                </div>
                {actionPlan.obstacle && (
                  <div>
                    <dt>可能的困难</dt>
                    <dd>{actionPlan.obstacle}</dd>
                  </div>
                )}
                {actionPlan.coping_plan && (
                  <div>
                    <dt>如果遇到困难</dt>
                    <dd>{actionPlan.coping_plan}</dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="empty-copy">
                系统不会替你安排任务。只有当你愿意尝试时，这里才会形成一个足够小的三天实验。
              </p>
            )}
          </section>

          {reviewerMode && <ReviewerPanel trace={trace} />}
        </aside>
      </main>
    </div>
  );
}

function ReviewerPanel({ trace }: { trace: ReviewerTrace | null }) {
  return (
    <section className="side-card reviewer-card">
      <div className="card-title">
        <div>
          <span className="eyebrow">评审可解释视图</span>
          <h3>本轮 AI 决策轨迹</h3>
        </div>
        <BrainCircuit size={20} />
      </div>

      {!trace ? (
        <p className="empty-copy">评审模式开启后再发送一条消息，即可查看状态、策略、检索和审核信息。</p>
      ) : (
        <div className="trace-stack">
          <TraceRow label="会话阶段" value={stageLabels[trace.stage] ?? trace.stage} />
          <TraceRow
            label="风险等级"
            value={trace.risk.level}
            tone={trace.risk.level === "HIGH" ? "danger" : trace.risk.level === "CONCERN" ? "warn" : "safe"}
          />
          <TraceRow
            label="关注问题"
            value={trace.focus_topic ? focusLabels[trace.focus_topic] ?? trace.focus_topic : "尚未聚焦"}
          />
          <TraceRow
            label="MI 策略"
            value={trace.mi_strategies.length ? trace.mi_strategies.join(" · ") : "安全流程优先"}
          />
          <TraceRow
            label="改变语言"
            value={trace.change_talk.length ? trace.change_talk.join("；") : "本轮未明确出现"}
          />
          <TraceRow
            label="维持语言"
            value={trace.sustain_talk.length ? trace.sustain_talk.join("；") : "本轮未明确出现"}
          />
          <TraceRow
            label="知识检索"
            value={trace.rag_used ? `${trace.knowledge_hits.length} 条命中` : "本轮无需检索"}
          />
          <TraceRow
            label="生成方式"
            value={trace.fallback_used ? "安全降级模板" : "LLM 实时生成"}
          />

          {trace.knowledge_hits.length > 0 && (
            <div className="knowledge-list">
              <span>检索依据</span>
              {trace.knowledge_hits.map((hit) => (
                <article key={hit.id}>
                  <strong>{hit.title}</strong>
                  <p>{hit.summary}</p>
                  {hit.source_url && (
                    <a href={hit.source_url} target="_blank" rel="noreferrer">
                      {hit.source_name ?? "查看来源"}
                    </a>
                  )}
                </article>
              ))}
            </div>
          )}

          <div className="quality-line">
            {trace.quality_flags.length === 0 ? (
              <>
                <CheckCircle2 size={16} /> 规则审核通过
              </>
            ) : (
              <>
                <AlertTriangle size={16} /> {trace.quality_flags.join(" · ")}
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function TraceRow({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "safe" | "warn" | "danger";
}) {
  return (
    <div className="trace-row">
      <span>{label}</span>
      <strong className={tone ? `tone-${tone}` : undefined}>{value}</strong>
    </div>
  );
}

export default App;
