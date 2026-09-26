"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useJobStore } from "@/store/jobStore";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// ── Types ──────────────────────────────────────────────────────────────────

interface Source {
  file_path: string;
  lines?: string;
}

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  timestamp: Date;
}

// ── Quick-prompt chips shown in empty state ────────────────────────────────

const QUICK_PROMPTS = [
  "Explain the main architecture",
  "Where are the API routes defined?",
  "List core dependencies",
  "How is authentication handled?",
  "What design patterns are used?",
];

// ── Typing indicator ───────────────────────────────────────────────────────

function TypingIndicator() {
  return (
    <div className="flex items-end gap-2">
      <div className="w-8 h-8 rounded-full bg-blue-700 flex items-center justify-center text-sm flex-shrink-0">
        🤖
      </div>
      <div className="bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-1.5">
        <span className="text-xs text-gray-400 mr-1">Analyzing codebase</span>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"
            style={{ animationDelay: `${i * 0.18}s` }}
          />
        ))}
      </div>
    </div>
  );
}

// ── Loading skeleton shown while waiting for LLM response ─────────────────

function ResponseSkeleton() {
  return (
    <div className="flex items-end gap-2">
      <div className="w-8 h-8 rounded-full bg-blue-700 flex items-center justify-center text-sm flex-shrink-0">
        🤖
      </div>
      <div className="flex flex-col gap-2 max-w-[65%] w-64">
        <div className="bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3 space-y-2">
          {/* Skeleton lines */}
          <div className="h-3 bg-gray-700 rounded animate-pulse w-full" />
          <div className="h-3 bg-gray-700 rounded animate-pulse w-5/6" />
          <div className="h-3 bg-gray-700 rounded animate-pulse w-4/6" />
          <div className="h-3 bg-gray-700 rounded animate-pulse w-3/4 mt-1" />
          <div className="h-3 bg-gray-700 rounded animate-pulse w-2/3" />
        </div>
        {/* Skeleton source tags */}
        <div className="flex gap-1.5 pl-1">
          <div className="h-5 w-28 bg-gray-800 rounded animate-pulse" />
          <div className="h-5 w-20 bg-gray-800 rounded animate-pulse" />
        </div>
      </div>
    </div>
  );
}

// ── Code block with copy button (used inside ReactMarkdown) ────────────────

function ChatCodeBlock({
  language,
  children,
}: {
  language: string;
  children: string;
}) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(children).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="rounded-lg overflow-hidden border border-gray-700 my-2">
      <div className="flex items-center justify-between bg-gray-900 px-3 py-1.5">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
          {language || "code"}
        </span>
        <button
          onClick={handleCopy}
          className="text-xs text-gray-400 hover:text-white transition-colors"
        >
          {copied ? "Copied!" : "Copy Code"}
        </button>
      </div>
      <SyntaxHighlighter
        language={language || "text"}
        style={vscDarkPlus}
        customStyle={{ margin: 0, borderRadius: 0, fontSize: "0.75rem" }}
        wrapLongLines
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
}

// ── Markdown renderer for assistant bubbles ────────────────────────────────

function AssistantMarkdown({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Multi-line fenced code block
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className ?? "");
          const isBlock = !props.ref && String(children).includes("\n");
          if (isBlock || match) {
            return (
              <ChatCodeBlock language={match?.[1] ?? ""}>
                {String(children).replace(/\n$/, "")}
              </ChatCodeBlock>
            );
          }
          // Inline code
          return (
            <code className="bg-gray-700 text-green-300 rounded px-1 py-0.5 text-xs font-mono">
              {children}
            </code>
          );
        },
        // Tables
        table({ children }) {
          return (
            <div className="overflow-x-auto my-2">
              <table className="text-xs border-collapse w-full">{children}</table>
            </div>
          );
        },
        th({ children }) {
          return (
            <th className="border border-gray-600 bg-gray-700 px-3 py-1.5 text-left font-semibold text-gray-200">
              {children}
            </th>
          );
        },
        td({ children }) {
          return (
            <td className="border border-gray-700 px-3 py-1.5 text-gray-300">
              {children}
            </td>
          );
        },
        // Lists
        ul({ children }) {
          return <ul className="list-disc list-inside space-y-0.5 my-1 text-sm">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="list-decimal list-inside space-y-0.5 my-1 text-sm">{children}</ol>;
        },
        // Paragraphs
        p({ children }) {
          return <p className="mb-1 last:mb-0 leading-relaxed">{children}</p>;
        },
        // Bold / strong
        strong({ children }) {
          return <strong className="font-semibold text-white">{children}</strong>;
        },
        // Block quote
        blockquote({ children }) {
          return (
            <blockquote className="border-l-2 border-blue-500 pl-3 text-gray-400 italic my-2">
              {children}
            </blockquote>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

// ── Source tags beneath assistant bubbles ─────────────────────────────────

function SourceTag({ source }: { source: Source }) {
  return (
    <button
      type="button"
      title={`${source.file_path}${source.lines ? `:${source.lines}` : ""}`}
      className="inline-flex items-center gap-1 font-mono text-xs bg-gray-900 border border-gray-700 text-blue-400 rounded px-2 py-0.5 hover:border-blue-500 hover:text-blue-300 transition-colors cursor-pointer"
    >
      <span>📄</span>
      <span>{source.file_path}</span>
      {source.lines && (
        <span className="text-gray-500">:{source.lines}</span>
      )}
    </button>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function OnboardingChat() {
  const job_id = useJobStore((s) => s.job_id);
  const job_status = useJobStore((s) => s.job_status);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll whenever messages or thinking state change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || thinking || !job_id) return;

      const userMsg: Message = {
        id: Date.now(),
        role: "user",
        content: trimmed,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setError(null);
      setThinking(true);

      try {
        const res = await fetch(`${API_BASE}/api/onboarding/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ job_id, query: trimmed }),
        });

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(
            (err as { detail?: string }).detail ?? `Server error ${res.status}`
          );
        }

        const data: { answer: string; sources?: Source[] } = await res.json();

        const assistantMsg: Message = {
          id: Date.now() + 1,
          role: "assistant",
          content: data.answer,
          sources: data.sources ?? [],
          timestamp: new Date(),
        };

        setMessages((prev) => [...prev, assistantMsg]);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Request failed.");
        // Remove the optimistically-added user message on error
        setMessages((prev) => prev.filter((m) => m.id !== userMsg.id));
      } finally {
        setThinking(false);
        textareaRef.current?.focus();
      }
    },
    [job_id, thinking]
  );

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  // ── Guardrail: index must be fully ingested before chatting ───────────
  if (!job_id || job_status !== "COMPLETED") {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-220px)] min-h-[400px] gap-4">
        <div className="bg-yellow-950 border border-yellow-800 rounded-xl px-6 py-5 text-yellow-300 text-sm max-w-md text-center">
          <p className="font-semibold text-base mb-1">Repository index not ready</p>
          <p className="text-yellow-400 text-xs">
            {job_status === "PENDING" || job_status === "PROCESSING"
              ? "Repository ingestion is still in progress. Please wait until it completes."
              : "Complete repository ingestion in the "}
            {job_status !== "PENDING" && job_status !== "PROCESSING" && (
              <span className="font-medium text-yellow-300">Project Setup</span>
            )}
            {job_status !== "PENDING" && job_status !== "PROCESSING" && (
              " tab before using the RepoVibe Chat."
            )}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-220px)] min-h-[500px]">
      {/* ── Header ── */}
      <div className="mb-4 flex-shrink-0">
        <h2 className="text-lg font-semibold text-white">RepoVibe Chat</h2>
        <p className="text-sm text-gray-400 mt-1">
          Query architectural insights, locate legacy logic, and understand
          code relationships using natural language.
        </p>
      </div>

      {/* ── Message list ── */}
      <div className="flex-1 overflow-y-auto space-y-5 pr-1">

        {/* Empty state — quick-prompt chips */}
        {messages.length === 0 && !thinking && (
          <div className="flex flex-col items-center gap-5 pt-10">
            <div className="w-12 h-12 rounded-full bg-blue-700 flex items-center justify-center text-2xl">
              🤖
            </div>
            <p className="text-gray-400 text-sm text-center max-w-xs">
              Ask anything about your repository. Try one of these to get started:
            </p>
            <div className="flex flex-wrap justify-center gap-2 max-w-lg">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => sendMessage(prompt)}
                  className="px-3 py-1.5 rounded-full border border-gray-600 bg-gray-800 hover:bg-gray-700 hover:border-blue-500 text-xs text-gray-300 hover:text-white transition-colors"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message bubbles */}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-blue-700 flex items-center justify-center text-sm flex-shrink-0 mt-1">
                🤖
              </div>
            )}

            <div className="flex flex-col gap-1.5 max-w-[75%]">
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm"
                    : "bg-gray-800 text-gray-200 rounded-bl-sm"
                }`}
              >
                {msg.role === "user" ? (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                ) : (
                  <AssistantMarkdown content={msg.content} />
                )}
                <p
                  className={`text-xs mt-1.5 ${
                    msg.role === "user" ? "text-blue-200" : "text-gray-600"
                  }`}
                >
                  {msg.timestamp.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </p>
              </div>

              {/* Source tags */}
              {msg.role === "assistant" &&
                msg.sources &&
                msg.sources.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pl-1">
                    {msg.sources.map((src, i) => (
                      <SourceTag key={i} source={src} />
                    ))}
                  </div>
                )}
            </div>

            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center text-sm flex-shrink-0 mt-1">
                👤
              </div>
            )}
          </div>
        ))}

        {/* Loading skeleton + typing indicator while waiting for LLM */}
        {thinking && (
          <>
            <TypingIndicator />
            <ResponseSkeleton />
          </>
        )}

        {/* Error banner */}
        {error && (
          <div className="bg-red-950 border border-red-800 rounded-xl px-4 py-3 text-red-400 text-sm">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* ── Pinned input bar ── */}
      <div className="mt-4 flex gap-2 items-end flex-shrink-0">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={thinking}
          placeholder={
            thinking
              ? "Analyzing codebase..."
              : "Ask about the codebase… (Enter to send, Shift+Enter for newline)"
          }
          rows={2}
          className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-200 resize-none focus:outline-none focus:border-blue-600 disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-gray-600"
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={thinking || !input.trim()}
          className="px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors text-white flex-shrink-0"
        >
          {thinking ? (
            <span className="flex items-center gap-1.5">
              <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              <span>Sending</span>
            </span>
          ) : (
            "Send"
          )}
        </button>
      </div>
    </div>
  );
}
