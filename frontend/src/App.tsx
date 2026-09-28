import {
  AlertTriangle,
  ArrowUp,
  Check,
  CircleHelp,
  Loader2,
  RotateCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { AGENT_NAME } from "./branding";
import type { ActionPlan, ChatResponse, Message, ReviewerTrace } from "./types";

const starterReplies = [
  "最近总是玩到很晚",
  "我想少玩，但停不下来",
  "父母根本不理解我",
  "游戏只是让我放松",
];

const focusLabels: Record<string, string> = {
  sleep: "睡眠",
  stopping: "停止困难",
  school: "学习与拖延",
  family: "家庭沟通",
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

const planStatusLabels: Record<ActionPlan["status"], string> = {
  active: "进行中",
  completed: "已完成",
  paused: "已暂停",
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
  const [loading, setLoading] = useState(false);
  const [streamingStarted, setStreamingStarted] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  const safetyActive =
    trace?.stage === "SAFETY" || trace?.risk.level === "HIGH";

  const insightItems = useMemo(() => {
    const items: string[] = [];
    const focus = trace?.focus_topic;

    if (focus === "sleep") items.push("游戏时间正在影响第二天的休息和精神状态");
    if (focus === "stopping") items.push("你正在关注能不能按自己的计划停下来");
    if (focus === "school") items.push("游戏和学习状态之间的影响已经被你注意到");
    if (focus === "family") items.push("你在意游戏之外，也在意自主感和家庭沟通");
    if (focus === "emotion") items.push("你正在观察游戏和情绪变化之间的关系");
    if (focus === "social") items.push("队友关系和下线边界都在影响你的选择");

    for (const need of trace?.psychological_needs ?? []) {
      const label = needLabels[need.name] ?? need.name;
      const sentence = `游戏对你来说也包含“${label}”这一部分`;
      if (!items.includes(sentence)) items.push(sentence);
    }

    if ((trace?.change_talk.length ?? 0) > 0) {
      items.push("你已经开始说出自己想改变或尝试的理由");
    }

    return items.slice(0, 3);
  }, [trace]);

  async function sendMessage(rawText: string) {
    const text = rawText.trim();
    if (!text || loading) return;

    const userMessage: Message = { id: createId(), role: "user", content: text };
    const assistantMessageId = createId();
    let assistantAdded = false;
    let completed = false;

    setMessages((current) => [...current, userMessage]);
    setInput("");
    setQuickReplies([]);
    setLoading(true);
    setStreamingStarted(false);
    setError(null);

    try {
      const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
          reviewer_mode: true,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error("服务暂时没有响应");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const processLine = (line: string) => {
        if (!line.trim()) return;

        const event = JSON.parse(line) as
          | { type: "start"; session_id: string }
          | {
              type: "meta";
              session_id: string;
              action_plan: ActionPlan | null;
              trace: ReviewerTrace | null;
            }
          | { type: "delta"; text: string }
          | { type: "done"; data: ChatResponse }
          | { type: "error"; message: string };

        if (event.type === "meta") {
          setActionPlan(event.action_plan);
          setTrace(event.trace);
          return;
        }

        if (event.type === "delta") {
          if (!assistantAdded) {
            assistantAdded = true;
            setStreamingStarted(true);
            setMessages((current) => [
              ...current,
              { id: assistantMessageId, role: "assistant", content: event.text },
            ]);
          } else {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantMessageId
                  ? { ...message, content: message.content + event.text }
                  : message,
              ),
            );
          }
          return;
        }

        if (event.type === "done") {
          completed = true;
          if (!assistantAdded) {
            assistantAdded = true;
            setMessages((current) => [
              ...current,
              { id: assistantMessageId, role: "assistant", content: event.data.reply },
            ]);
          } else {
            setMessages((current) =>
              current.map((message) =>
                message.id === assistantMessageId
                  ? { ...message, content: event.data.reply }
                  : message,
              ),
            );
          }
          setQuickReplies(event.data.quick_replies);
          setActionPlan(event.data.action_plan);
          setTrace(event.data.trace);
          return;
        }

        if (event.type === "error") {
          throw new Error(event.message);
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          processLine(line);
        }
      }

      buffer += decoder.decode();
      if (buffer.trim()) processLine(buffer);

      if (!completed) {
        throw new Error("流式响应未完整结束");
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "发送失败");
      setQuickReplies(["重新发送", "先缓一缓"]);
    } finally {
      setLoading(false);
      setStreamingStarted(false);
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

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-wordmark">
          <span className="brand-mark" aria-hidden="true">
            <span />
          </span>
          <div className="brand-copy">
            <div className="brand-title-row">
              <h1>{AGENT_NAME}</h1>
              <span className="brand-context">游戏行为支持</span>
            </div>
            <p>帮你看清发生了什么，再决定下一步怎么走。</p>
          </div>
        </div>

        <button className="reset-button" type="button" onClick={() => void resetSession()}>
          <RotateCcw size={15} strokeWidth={1.9} />
          <span>重新开始</span>
        </button>
      </header>

      <div className={`system-strip ${safetyActive ? "safety-strip" : ""}`}>
        <div className="system-strip-inner">
          <div className="system-strip-copy">
            {safetyActive ? <AlertTriangle size={15} /> : <ShieldCheck size={15} />}
            <span>
              {safetyActive
                ? "安全优先模式已开启。当前先确认你是否安全，并连接现实中的支持。"
                : "匿名对话 · 不进行医学诊断 · 不替代专业帮助"}
            </span>
          </div>
          {!safetyActive && (
            <button
              type="button"
              className="help-link"
              onClick={() => void sendMessage("我现在感觉很危险，需要马上获得帮助")}
            >
              我现在需要帮助
            </button>
          )}
        </div>
      </div>

      <main className="workspace">
        <section className={`conversation-column ${safetyActive ? "safety-conversation" : ""}`} aria-label="对话区">
          <div className="conversation-head">
            <div>
              <span className="section-kicker">匿名对话</span>
              <h2>先从你最在意的事情开始</h2>
              <p>不用先想好答案，也不用证明自己做得对不对。</p>
            </div>
            <div className="privacy-note">
              <ShieldCheck size={14} />
              不需要真实姓名或学校
            </div>
          </div>

          <div className="messages" aria-live="polite">
            {messages.map((message) => (
              <article key={message.id} className={`message ${message.role}`}>
                <div className="message-meta">
                  <span className={`speaker-dot ${message.role}`} aria-hidden="true" />
                  <span>{message.role === "assistant" ? AGENT_NAME : "你"}</span>
                </div>
                <div className="message-content">
                  <p>{message.content}</p>
                </div>
              </article>
            ))}

            {loading && !streamingStarted && (
              <article className="message assistant">
                <div className="message-meta">
                  <span className="speaker-dot assistant" aria-hidden="true" />
                  <span>{AGENT_NAME}</span>
                </div>
                <div className="message-content loading-message">
                  <p>
                    <Loader2 className="spin" size={15} />
                    正在理解你刚才说的重点……
                  </p>
                </div>
              </article>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="conversation-tools">
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
                <AlertTriangle size={16} />
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
                placeholder="说说最近发生了什么……"
                maxLength={3000}
                disabled={loading}
              />
              <div className="composer-footer">
                <span>Enter 发送 · Shift + Enter 换行</span>
                <button className="send-button" type="submit" disabled={!input.trim() || loading} aria-label="发送">
                  <ArrowUp size={17} strokeWidth={2.2} />
                </button>
              </div>
            </form>
          </div>
        </section>

        <aside className={`progress-panel ${safetyActive ? "safety-progress" : ""}`} aria-label={safetyActive ? "安全优先状态" : "对话进展"}>
          {safetyActive ? (
            <>
              <div className="progress-header safety-progress-header">
                <div>
                  <span className="section-kicker danger-kicker">安全优先</span>
                  <h3>当前先确认你的安全</h3>
                </div>
                <AlertTriangle size={18} />
              </div>

              <p className="progress-lead">
                普通的游戏建议和行动实验已经暂停。现在先确认你是否安全，并尽快连接现实中的可信任支持。
              </p>

              <div className="safety-steps">
                <div>
                  <span>01</span>
                  <p>先远离可能伤害到你的东西或危险位置。</p>
                </div>
                <div>
                  <span>02</span>
                  <p>尽量不要独处，去有其他人的地方。</p>
                </div>
                <div>
                  <span>03</span>
                  <p>联系可信任的成年人；如果可能马上行动，请联系当地紧急救援。</p>
                </div>
              </div>

              <div className="safety-footnote">
                只有在你明确说明当前安全，并且没有立即伤害自己的打算或已经有人陪伴后，系统才会退出安全优先模式。
              </div>
            </>
          ) : (
            <>
              <div className="progress-header">
                <div>
                  <span className="section-kicker">对话进展</span>
                  <h3>你正在慢慢看清的事情</h3>
                </div>
                <Sparkles size={17} strokeWidth={1.8} />
              </div>

              <section className="progress-section">
                <div className="progress-section-title">
                  <span>目前关注</span>
                  <small>01</small>
                </div>
                {balanceItems.length > 0 ? (
                  <div className="tag-list">
                    {balanceItems.map((item) => (
                      <span key={item}>{item}</span>
                    ))}
                  </div>
                ) : (
                  <p className="progress-empty">聊几句后，这里会出现你自己提到的关注点。</p>
                )}
                <div className="evidence-note">
                  <CircleHelp size={14} />
                  只整理你已经说出的内容，不给你贴标签。
                </div>
              </section>

              <section className="progress-section">
                <div className="progress-section-title">
                  <span>我正在发现</span>
                  <small>02</small>
                </div>
                {insightItems.length > 0 ? (
                  <div className="insight-list">
                    {insightItems.map((item) => (
                      <p key={item}>{item}</p>
                    ))}
                  </div>
                ) : (
                  <p className="progress-empty">现在不用急着下结论，先把真实体验聊清楚。</p>
                )}
              </section>

              <section className="progress-section experiment-section">
                <div className="progress-section-title">
                  <span>我的小实验</span>
                  <small>03</small>
                </div>

                {actionPlan ? (
                  <div className="experiment">
                    <div className="experiment-heading">
                      <div>
                        <span className="status-dot" />
                        <strong>{actionPlan.title}</strong>
                      </div>
                      <span className="status-text">{planStatusLabels[actionPlan.status]}</span>
                    </div>

                    <div className="experiment-main">
                      <span>我要尝试</span>
                      <p>{actionPlan.behavior}</p>
                    </div>

                    <dl className="experiment-details">
                      <div>
                        <dt>持续时间</dt>
                        <dd>{actionPlan.duration}</dd>
                      </div>
                      <div>
                        <dt>我的原因</dt>
                        <dd>{actionPlan.reason}</dd>
                      </div>
                      <div>
                        <dt>复盘</dt>
                        <dd>{actionPlan.successes} / {actionPlan.attempts} 次有效记录</dd>
                      </div>
                      {actionPlan.obstacle && (
                        <div>
                          <dt>可能的困难</dt>
                          <dd>{actionPlan.obstacle}</dd>
                        </div>
                      )}
                      {actionPlan.coping_plan && (
                        <div>
                          <dt>遇到困难时</dt>
                          <dd>{actionPlan.coping_plan}</dd>
                        </div>
                      )}
                      {actionPlan.last_review && (
                        <div>
                          <dt>最近复盘</dt>
                          <dd>{actionPlan.last_review}</dd>
                        </div>
                      )}
                    </dl>
                  </div>
                ) : (
                  <div className="experiment-empty">
                    <span className="experiment-icon">
                      <Check size={15} />
                    </span>
                    <p>当你自己提出一个想尝试的改变时，这里会把它整理成一个可观察的小实验。</p>
                  </div>
                )}
              </section>
            </>
          )}
        </aside>
      </main>
    </div>
  );
}

export default App;
