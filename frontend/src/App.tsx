import {
  AlertTriangle,
  Bot,
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
        <div className="brand-block">
          <div className="brand-icon" aria-hidden="true">
            <Gamepad2 size={24} />
          </div>
          <div>
            <div className="brand-line">
              <h1>{AGENT_NAME}</h1>
              <span>Re:Play</span>
            </div>
            <p>不是逼你离开游戏，而是帮你重新拿回选择权。</p>
          </div>
        </div>

        <div className="top-actions">
          <button className="icon-button" type="button" onClick={() => void resetSession()}>
            <RefreshCw size={18} />
            <span>重新开始</span>
          </button>
        </div>
      </header>

      <div className={`prototype-notice ${safetyActive ? "safety-active-notice" : ""}`}>
        {safetyActive ? <AlertTriangle size={16} /> : <ShieldCheck size={16} />}
        <span>
          {safetyActive
            ? "安全优先模式已开启：先确认你当前是否安全，并连接现实中的支持。"
            : "提供心理支持与风险识别，不进行医学诊断，也不能替代专业帮助。"}
        </span>
        {!safetyActive && (
          <button
            type="button"
            onClick={() => void sendMessage("我现在感觉很危险，需要马上获得帮助")}
          >
            我现在需要帮助
          </button>
        )}
      </div>

      <main className="main-layout">
        <section className={`chat-panel ${safetyActive ? "safety-chat" : ""}`} aria-label="对话区">
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
                  <span>{message.role === "assistant" ? AGENT_NAME : "我"}</span>
                  <p>{message.content}</p>
                </div>
              </article>
            ))}

            {loading && !streamingStarted && (
              <article className="message assistant">
                <div className="avatar" aria-hidden="true">
                  <Bot size={19} />
                </div>
                <div className="message-body loading-message">
                  <span>{AGENT_NAME}</span>
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
              placeholder="可以说说最近一次让你在意的游戏体验……"
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

        <aside className="side-panel" aria-label={safetyActive ? "安全优先状态" : "对话进展"}>
          {safetyActive ? (
            <section className="side-card safety-priority-card">
              <div className="card-title">
                <div>
                  <span className="eyebrow">安全优先</span>
                  <h3>当前先确认你的安全</h3>
                </div>
                <AlertTriangle size={20} />
              </div>

              <p className="safety-priority-copy">
                系统已暂停普通的游戏建议和行动实验。接下来的重点是确认你现在是否安全，并尽快连接现实中的可信任支持。
              </p>

              <div className="safety-step-list">
                <div>
                  <strong>1</strong>
                  <span>先远离可能伤害到你的东西或危险位置。</span>
                </div>
                <div>
                  <strong>2</strong>
                  <span>尽量不要独处，去有其他人的地方。</span>
                </div>
                <div>
                  <strong>3</strong>
                  <span>联系可信任的成年人；如果可能马上行动，请联系当地紧急救援。</span>
                </div>
              </div>

              <div className="safety-state-note">
                只有在你明确说明当前安全，并且没有立即伤害自己的打算或已经有人陪伴后，系统才会退出安全优先模式。
              </div>
            </section>
          ) : (
            <>
              <section className="side-card balance-card">
                <div className="card-title">
                  <div>
                    <span className="eyebrow">目前关注</span>
                    <h3>这次对话正在谈什么</h3>
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
                  <p className="empty-copy">聊几句后，这里会逐渐出现你自己提到的关注点。</p>
                )}

                <div className="balance-note">
                  <CircleHelp size={16} />
                  只根据你已经说出的内容整理，不给你贴标签。
                </div>
              </section>

              <section className="side-card balance-card">
                <div className="card-title">
                  <div>
                    <span className="eyebrow">我正在发现</span>
                    <h3>从对话里慢慢看清的事情</h3>
                  </div>
                  <Sparkles size={19} />
                </div>

                {insightItems.length > 0 ? (
                  <div className="plan-grid">
                    {insightItems.map((item) => (
                      <div key={item}>
                        <dd>{item}</dd>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="empty-copy">现在还不用急着下结论，先把你的真实体验聊清楚。</p>
                )}
              </section>

              <section className="side-card plan-card">
                <div className="card-title">
                  <div>
                    <span className="eyebrow">我的小实验</span>
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
                      <dt>当前状态</dt>
                      <dd>{planStatusLabels[actionPlan.status]}</dd>
                    </div>
                    <div>
                      <dt>复盘记录</dt>
                      <dd>{actionPlan.successes} 次有效尝试 / {actionPlan.attempts} 次记录</dd>
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
                        <dt>最近一次复盘</dt>
                        <dd>{actionPlan.last_review}</dd>
                      </div>
                    )}
                  </dl>
                ) : (
                  <p className="empty-copy">
                    当你自己提出一个想尝试的改变时，这里会把它整理成一个可观察的小实验。
                  </p>
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
