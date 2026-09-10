import { Fragment, useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Check,
  CircleHelp,
  Fuel,
  Leaf,
  LoaderCircle,
  MessageSquare,
  Plus,
  ShoppingBasket,
  Sparkles,
  Terminal,
  Wallet,
  X,
} from "lucide-react";
import Markdown from "react-markdown";
import "./App.css";

import type { Message, Card, ChatResponse, Comparison } from "./types";
import { CardResult } from "./components/CardResult";
import { ComparisonSummary } from "./components/ComparisonSummary";
import { BrandMark, Wordmark } from "./components/Brand";

const suggestions = [
  {
    icon: ShoppingBasket,
    title: "The everyday essentials",
    detail: "Groceries, dining & everything in between",
    prompt: "I spend mostly on groceries and dining. Which cards fit me?",
  },
  {
    icon: Fuel,
    title: "More miles. More rewards.",
    detail: "Gas, commuting & the daily drive",
    prompt: "I commute every day and spend a lot on gas. Which cards fit me?",
  },
  {
    icon: Wallet,
    title: "Ready for takeoff",
    detail: "Travel, hotels & spending abroad",
    prompt: "I travel abroad and book flights and hotels. Which cards fit me?",
  },
];

export default function App() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [cards, setCards] = useState<Card[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [source, setSource] = useState<"live" | "agent">("live");
  const [busy, setBusy] = useState(false);
  const [matching, setMatching] = useState(false);
  const [matched, setMatched] = useState(false);
  const [error, setError] = useState("");
  const [matchError, setMatchError] = useState("");
  const [failedMessage, setFailedMessage] = useState("");
  const [tab, setTab] = useState<"chat" | "matches">("chat");
  const [help, setHelp] = useState(false);
  const [showJump, setShowJump] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const helpDialog = useRef<HTMLDialogElement>(null);
  const helpButton = useRef<HTMLButtonElement>(null);
  const stickToBottom = useRef(true);
  const version = useRef(0);
  const liveRequest = useRef<AbortController | null>(null);
  const chatRequest = useRef<AbortController | null>(null);
  const sending = useRef(false);
  const latestCards = useRef<{
    cards: Card[];
    comparison: Comparison | null;
    source: "live" | "agent";
    matched: boolean;
  }>({ cards: [], comparison: null, source: "live", matched: false });

  function invalidateLive() {
    version.current += 1;
    liveRequest.current?.abort();
    setMatching(false);
  }

  useEffect(() => {
    if (!draft.trim() || busy) return;
    const revision = version.current;
    const controller = new AbortController();
    liveRequest.current = controller;
    const timeout = setTimeout(async () => {
      setMatching(true);
      setMatchError("");
      try {
        const res = await fetch("/api/match", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: draft }),
          signal: controller.signal,
        });
        if (!res.ok)
          throw new Error(
            "Live matching is unavailable. Try editing your message again.",
          );
        const data = await res.json();
        if (!Array.isArray(data.matches))
          throw new Error("Could not load card matches.");
        if (revision !== version.current || controller.signal.aborted) return;
        setCards(data.matches);
        setComparison(data.comparison ?? null);
        setSource("live");
        setMatched(true);
      } catch (e) {
        if (!controller.signal.aborted && revision === version.current)
          setMatchError(
            e instanceof Error ? e.message : "Could not load card matches.",
          );
      } finally {
        if (revision === version.current && !controller.signal.aborted)
          setMatching(false);
      }
    }, 350);
    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [draft, busy]);

  useEffect(() => {
    if (messages.length && stickToBottom.current)
      log.current?.scrollTo({
        top: log.current.scrollHeight,
        behavior: "smooth",
      });
  }, [messages, busy, error]);

  useEffect(() => {
    if (help) helpDialog.current?.showModal();
    else if (helpDialog.current?.open) {
      helpDialog.current.close();
      helpButton.current?.focus();
    }
  }, [help]);

  useEffect(
    () => () => {
      liveRequest.current?.abort();
      chatRequest.current?.abort();
    },
    [],
  );

  function changeDraft(value: string) {
    invalidateLive();
    setDraft(value);
    setMatchError("");
    if (!value.trim()) {
      setCards(latestCards.current.cards);
      setComparison(latestCards.current.comparison);
      setSource(latestCards.current.source);
      setMatched(latestCards.current.matched);
    }
  }

  async function send(text = draft, retry = false) {
    text = text.trim();
    if (!text || sending.current) return;
    sending.current = true;
    invalidateLive();
    const revision = version.current;
    const previous = retry ? messages.slice(0, -1) : messages;
    const next: Message[] = [...previous, { role: "user", content: text }];
    setMessages(next);
    setDraft("");
    setBusy(true);
    setError("");
    setMatchError("");
    setFailedMessage("");
    setTab("chat");
    stickToBottom.current = true;
    const controller = new AbortController();
    chatRequest.current = controller;
    const timeout = setTimeout(() => controller.abort(), 90000);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: previous.slice(-12) }),
        signal: controller.signal,
      });
      const data: ChatResponse = await res.json();
      if (revision !== version.current) return;
      if (Array.isArray(data.cards)) {
        const result = {
          cards: data.cards,
          comparison: data.comparison ?? null,
          source:
            data.source === "agent" ? ("agent" as const) : ("live" as const),
          matched: true,
        };
        latestCards.current = result;
        setCards(result.cards);
        setComparison(result.comparison);
        setSource(result.source);
        setMatched(true);
      }
      if (!res.ok || data.error)
        throw new Error(
          data.error || "The assistant could not answer. Please try again.",
        );
      if (!data.reply)
        throw new Error(
          "The assistant returned an empty answer. Please try again.",
        );
      setMessages([...next, { role: "assistant", content: data.reply }]);
    } catch (e) {
      if (revision !== version.current) return;
      setError(
        controller.signal.aborted
          ? "The response took too long. Please try again."
          : e instanceof Error && !(e instanceof SyntaxError)
            ? e.message
            : "Could not connect to the assistant. Please try again.",
      );
      setFailedMessage(text);
    } finally {
      clearTimeout(timeout);
      if (revision === version.current) {
        sending.current = false;
        setBusy(false);
        requestAnimationFrame(() => input.current?.focus());
      }
    }
  }

  function reset() {
    invalidateLive();
    chatRequest.current?.abort();
    sending.current = false;
    setMessages([]);
    setCards([]);
    setComparison(null);
    setDraft("");
    setBusy(false);
    setError("");
    setMatchError("");
    setFailedMessage("");
    setMatched(false);
    setTab("chat");
    setShowJump(false);
    latestCards.current = {
      cards: [],
      comparison: null,
      source: "live",
      matched: false,
    };
    requestAnimationFrame(() => input.current?.focus());
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send();
  }
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      void send();
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#composer">
        Skip to message input
      </a>
      <aside className="rail" aria-label="Workspace">
        <a href="/" className="brand-mark" aria-label="WalletSync home">
          <BrandMark size={44} />
        </a>
        <span className="rail-divider" />
        <span className="rail-active" title="Card assistant">
          <MessageSquare size={20} />
        </span>
        <span className="rail-word">A BETTER FIT.</span>
        <Leaf className="rail-leaf" size={20} />
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="brand-lockup">
            <a className="brand" href="/" aria-label="WalletSync home">
              <span className="header-symbol">
                <BrandMark size={36} />
              </span>
              <Wordmark />
            </a>
            <span className="workspace-label">Your spending, in sync.</span>
          </div>
          <div className="header-actions">
            <span className="session-label">
              <span className="status-dot" />
              Current session
            </span>
            <button
              ref={helpButton}
              className="icon-button"
              aria-label="How WalletSync works"
              onClick={() => setHelp(true)}
            >
              <CircleHelp size={19} />
            </button>
          </div>
        </header>
        <div className="workspace-bar">
          <div className="breadcrumb">
            <Terminal size={16} />
            <span>Workspace</span>
            <span className="slash">/</span>
            <strong>Card assistant</strong>
          </div>
          <button className="new-chat" onClick={reset}>
            <Plus size={15} />
            New chat
          </button>
        </div>
        <nav className="mobile-tabs" aria-label="Workspace panels">
          <button aria-pressed={tab === "chat"} onClick={() => setTab("chat")}>
            Conversation
          </button>
          <button
            aria-pressed={tab === "matches"}
            onClick={() => setTab("matches")}
          >
            Matches {cards.length > 0 && <span>{cards.length}</span>}
          </button>
        </nav>
        <main className="main-grid">
          <section
            className={`conversation ${tab === "chat" ? "mobile-active" : ""}`}
            aria-label="Card conversation"
          >
            <div
              className="conversation-scroll"
              ref={log}
              onScroll={() => {
                const box = log.current;
                if (box) {
                  stickToBottom.current =
                    box.scrollHeight - box.scrollTop - box.clientHeight < 90;
                  setShowJump(!stickToBottom.current);
                }
              }}
            >
              {messages.length === 0 ? (
                <div className="welcome">
                  <div className="intro-label">
                    <span className="intro-line" />
                    LESS GUESSWORK. BETTER CARDS.
                  </div>
                  <h1>
                    Your spending.
                    <br />A card that <span>gets it.</span>
                  </h1>
                  <p className="welcome-copy">
                    Tell us what everyday looks like. Find cards that fit,
                    <br className="desktop-break" /> then get to know the fine
                    print.
                  </p>
                  <div className="suggestions">
                    {suggestions.map(
                      ({ icon: Icon, title, detail, prompt }) => (
                        <button
                          className="suggestion"
                          key={title}
                          onClick={() => {
                            changeDraft(prompt);
                            input.current?.focus();
                          }}
                        >
                          <span className="suggestion-icon">
                            <Icon size={19} />
                          </span>
                          <span>
                            <strong>{title}</strong>
                            <small>{detail}</small>
                          </span>
                          <ArrowRight size={17} className="suggestion-arrow" />
                        </button>
                      ),
                    )}
                  </div>
                  <div className="welcome-note">
                    <Check size={14} />
                    Find the benefits that matter to your everyday
                  </div>
                </div>
              ) : (
                <div
                  className="message-list"
                  role="log"
                  aria-label="Conversation"
                  aria-live="polite"
                  aria-relevant="additions"
                >
                  <div className="conversation-date">
                    YOUR CARD CONVERSATION
                  </div>
                  {messages.map((message, i) => (
                    <article className={`message ${message.role}`} key={i}>
                      <div className="message-avatar">
                        {message.role === "assistant" ? (
                          <BrandMark size={30} />
                        ) : (
                          "Y"
                        )}
                      </div>
                      <div className="message-content">
                        <div className="message-author">
                          {message.role === "assistant" ? "WalletSync" : "You"}
                          {message.role === "assistant" && (
                            <span>ASSISTANT</span>
                          )}
                        </div>
                        <div className="message-body">
                          {message.role === "user" ? (
                            message.content
                          ) : (
                            <Markdown
                              skipHtml
                              components={{
                                img: ({ alt }) => <span>{alt}</span>,
                              }}
                            >
                              {message.content}
                            </Markdown>
                          )}
                        </div>
                      </div>
                    </article>
                  ))}
                  {busy && (
                    <div className="thinking" role="status">
                      <LoaderCircle size={17} className="spin" />
                      <span>Looking into your cards...</span>
                    </div>
                  )}
                  {error && (
                    <div className="error-box" role="alert">
                      <p>{error}</p>
                      <button
                        onClick={() => void send(failedMessage, true)}
                        disabled={busy}
                      >
                        Try again <ArrowRight size={14} />
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="composer-area">
              {showJump && (
                <button
                  className="jump-button"
                  onClick={() => {
                    stickToBottom.current = true;
                    log.current?.scrollTo({
                      top: log.current.scrollHeight,
                      behavior: "smooth",
                    });
                  }}
                >
                  Latest messages <ArrowDown size={14} />
                </button>
              )}
              <form
                className={`composer ${busy ? "is-busy" : ""}`}
                onSubmit={submit}
              >
                <label className="sr-only" htmlFor="composer">
                  Tell us about your spending or ask about a card
                </label>
                <textarea
                  id="composer"
                  ref={input}
                  value={draft}
                  onChange={(e) => changeDraft(e.target.value)}
                  onKeyDown={onKeyDown}
                  placeholder="I spend mostly on groceries, gas and a little adventure..."
                  maxLength={8000}
                  disabled={busy}
                  rows={2}
                />
                <div className="composer-bottom">
                  <span>
                    <span className={`status-dot ${busy ? "working" : ""}`} />
                    {busy
                      ? "Reading the fine print"
                      : "Start with how you spend"}
                  </span>
                  <button
                    className="send-button"
                    type="submit"
                    disabled={!draft.trim() || busy}
                    aria-label="Send message"
                  >
                    {busy ? (
                      <LoaderCircle size={18} className="spin" />
                    ) : (
                      <ArrowUp size={19} />
                    )}
                  </button>
                </div>
              </form>
              <div className="composer-hint">
                <span>
                  <kbd>Enter</kbd> to send
                  <span className="hint-separator">·</span>
                  <kbd>Shift + Enter</kbd> for a new line
                </span>
                <span>
                  {draft.length > 7500
                    ? `${draft.length}/8000`
                    : "A little clarity goes a long way."}
                </span>
              </div>
            </div>
          </section>
          <aside
            className={`matches-panel ${tab === "matches" ? "mobile-active" : ""}`}
            aria-label="Card matches"
          >
            <div className="matches-heading">
              <div>
                <span className="eyebrow">THE SHORTLIST</span>
                <h2>
                  Your card matches
                  <span>
                    {cards.length > 0
                      ? String(cards.length).padStart(2, "0")
                      : "00"}
                  </span>
                </h2>
              </div>
              <span className="match-indicator" title="Updates as you type">
                <span className="status-dot" />
                LIVE
              </span>
            </div>
            <div className="match-status" role="status">
              {matching ? (
                <>
                  <LoaderCircle size={13} className="spin" />
                  Finding your fit...
                </>
              ) : matched ? (
                <>
                  <Check size={13} />
                  {comparison
                    ? "Compared for your spending"
                    : source === "agent"
                      ? "Recommended by your assistant"
                      : "Matched to your spending"}
                </>
              ) : (
                "A good match starts with you."
              )}
            </div>
            {comparison && (
              <button
                className="comparison-jump"
                onClick={() =>
                  document
                    .getElementById("comparison-summary")
                    ?.scrollIntoView({ behavior: "auto", block: "start" })
                }
              >
                See how they compare <ArrowDown size={14} />
              </button>
            )}
            <div className="matches-scroll" aria-busy={matching}>
              {matchError && (
                <div className="match-error" role="alert">
                  {matchError}
                </div>
              )}
              {cards.length ? (
                <div className="card-list">
                  {cards.map((card, i) => (
                    <Fragment key={card.card_id}>
                      {i === 1 && comparison && (
                        <h3 className="alternatives-heading">
                          Other cards to consider
                        </h3>
                      )}
                      <CardResult
                        card={card}
                        featured={card.card_id === comparison?.card_id}
                        onAsk={(text) => void send(text)}
                        disabled={busy}
                      />
                    </Fragment>
                  ))}
                  {comparison && <ComparisonSummary comparison={comparison} />}
                </div>
              ) : (
                <div className="matches-empty">
                  <div className="empty-art" aria-hidden="true">
                    <div className="illustration-card back" />
                    <div className="illustration-card front">
                      <span className="illustration-chip" />
                      <Wallet size={20} />
                      <span className="illustration-number">
                        •••• &nbsp; •••• &nbsp; ••••
                      </span>
                      <span className="illustration-line" />
                    </div>
                    <span className="art-spark">
                      <Sparkles size={18} />
                    </span>
                  </div>
                  <h3>
                    {matched ? "No matches this time" : "Meet your next card."}
                  </h3>
                  <p>
                    {matched
                      ? "Try describing your everyday spending in a little more detail."
                      : "As you type, we’ll connect your everyday spending to cards worth a closer look."}
                  </p>
                  <div className="empty-categories">
                    <span>Groceries</span>
                    <span>Travel</span>
                    <span>Dining</span>
                  </div>
                </div>
              )}
            </div>
            <footer className="matches-footer">
              <Leaf size={15} />
              <p>
                Built around your spending.
                <br />
                <span>Always check the latest issuer terms.</span>
              </p>
            </footer>
          </aside>
        </main>
        <footer className="app-footer">
          <span>SMALL DECISIONS. SMARTER SPENDING.</span>
          <span>
            <Wordmark compact />
          </span>
        </footer>
      </div>
      <dialog
        ref={helpDialog}
        className="help-dialog"
        aria-labelledby="help-title"
        onCancel={() => setHelp(false)}
        onClose={() => setHelp(false)}
      >
        <div className="help-header">
          <BrandMark size={40} />
          <button
            className="icon-button"
            aria-label="Close help"
            onClick={() => setHelp(false)}
          >
            <X size={20} />
          </button>
        </div>
        <h2 id="help-title">A little help finding your fit.</h2>
        <p>
          Describe your spending to explore cards and compare their benefits.
          Ask about rewards, fees and the tradeoffs that matter to you.
        </p>
        <p>
          Live matches use spending categories, earn rates and fees. They are a
          starting point, not an estimate of your cash savings.
        </p>
        <p>
          Your conversation stays in this tab and clears when you refresh or
          start a new chat. Messages are sent to the server and AWS Bedrock to
          generate replies. No application is submitted.
        </p>
        <button className="help-done" onClick={() => setHelp(false)}>
          Got it <Check size={16} />
        </button>
      </dialog>
    </div>
  );
}
