"use client";

/**
 * OnboardingChat – Tab 3
 *
 * An interactive chat interface for querying architecture insights.
 * Questions are answered client-side with a mock AI that responds to
 * keywords; swap the `_generateReply` function for a real LLM API call
 * when a backend chat endpoint is available.
 */

import { useEffect, useRef, useState } from "react";

// ── Types ──────────────────────────────────────────────────────────────────

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

// ── Mock AI reply logic ────────────────────────────────────────────────────

const KNOWLEDGE_BASE: Array<[RegExp, string]> = [
  [
    /microservice|service|decompos/i,
    "**Microservice decomposition** works by identifying bounded contexts in your monolith — each cohesive group of responsibilities becomes an independent service with its own data store and API. The Code Modernizer tab can give you a starting blueprint from your existing code.",
  ],
  [
    /terraform|tf|infra/i,
    "**Terraform** best practices include pinning provider versions, splitting state by environment, using remote state (S3 + DynamoDB lock), and always running `terraform plan` in CI before `apply`. The Cloud Optimizer can scan your `.tf` files for common mis-configurations.",
  ],
  [
    /kubernetes|k8s|yaml|manifest/i,
    "For **Kubernetes** production readiness, ensure every pod has resource `requests` and `limits`, liveness/readiness probes, and a non-root security context. Drop unnecessary capabilities and avoid `hostNetwork`. Use the Cloud Optimizer to get a detailed audit.",
  ],
  [
    /security|vulnerability|cve|secret/i,
    "**Security hardening** checklist: never embed secrets in manifests — use Kubernetes Secrets or a vault; restrict RBAC to least-privilege; scan images with Trivy or Grype; enable PodSecurity admission policies.",
  ],
  [
    /cost|expensive|pricing|bill/i,
    "**Cost optimisation** tips: right-size instances using Compute Optimiser recommendations; use Spot/Preemptible nodes for stateless workloads; enable cluster autoscaler; review unused Elastic IPs and snapshots. The Cloud Optimizer flags oversized or burstable instance choices.",
  ],
  [
    /fastapi|python|backend/i,
    "The **FastAPI** backend in this project exposes `/api/refactor` (code modernisation) and `/api/optimize` (IaC analysis). Both endpoints accept multipart form data so you can submit raw text or a file upload. Swagger docs are at `http://localhost:8000/docs`.",
  ],
  [
    /next|react|frontend/i,
    "The **Next.js** frontend uses the App Router with Tailwind CSS for styling. Each tab (`Code Modernizer`, `Cloud Optimizer`, `Onboarding Chat`) is a self-contained React component that calls the FastAPI backend at `http://localhost:8000`.",
  ],
  [
    /hello|hi|hey|howdy/i,
    "👋 Hello! I'm the ArchModernizer AI assistant. Ask me about **microservice decomposition**, **Terraform**, **Kubernetes**, **security hardening**, **cost optimisation**, or how the project itself works.",
  ],
];

function _generateReply(message: string): Promise<string> {
  return new Promise((resolve) => {
    // Simulate network latency
    setTimeout(() => {
      for (const [pattern, response] of KNOWLEDGE_BASE) {
        if (pattern.test(message)) {
          resolve(response);
          return;
        }
      }
      resolve(
        "That's a great question! For detailed architecture guidance, try asking about **microservices**, **Terraform**, **Kubernetes**, **security**, or **cost optimisation**. I can also explain how the backend `/api/refactor` or `/api/optimize` endpoints work."
      );
    }, 600 + Math.random() * 600);
  });
}

// ── Helpers ────────────────────────────────────────────────────────────────

function formatTime(d: Date) {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

/** Render simple markdown-style bold (**text**) */
function RichText({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("**") && part.endsWith("**") ? (
          <strong key={i}>{part.slice(2, -2)}</strong>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

// ── Component ──────────────────────────────────────────────────────────────

const INITIAL_MESSAGE: Message = {
  id: 0,
  role: "assistant",
  content:
    "👋 Welcome to **ArchModernizer AI**! I can help you understand microservice decomposition, Terraform and Kubernetes best practices, security hardening, and cost optimisation. What would you like to explore?",
  timestamp: new Date(),
};

export default function OnboardingChat() {
  const [messages, setMessages] = useState<Message[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  async function sendMessage() {
    const text = input.trim();
    if (!text || thinking) return;

    const userMsg: Message = {
      id: Date.now(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setThinking(true);

    const reply = await _generateReply(text);
    const assistantMsg: Message = {
      id: Date.now() + 1,
      role: "assistant",
      content: reply,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, assistantMsg]);
    setThinking(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-220px)] min-h-[500px]">
      {/* ── Header ── */}
      <div className="mb-4">
        <h2 className="text-lg font-semibold">Onboarding Chat</h2>
        <p className="text-sm text-gray-400 mt-1">
          Ask about architecture patterns, Terraform best practices, Kubernetes
          hardening, or how this project is built.
        </p>
      </div>

      {/* ── Message list ── */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-full bg-blue-700 flex items-center justify-center text-sm mr-2 flex-shrink-0 mt-1">
                🤖
              </div>
            )}
            <div
              className={`max-w-[70%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-br-sm"
                  : "bg-gray-800 text-gray-200 rounded-bl-sm"
              }`}
            >
              <p>
                <RichText text={msg.content} />
              </p>
              <p
                className={`text-xs mt-1 ${
                  msg.role === "user" ? "text-blue-200" : "text-gray-500"
                }`}
              >
                {formatTime(msg.timestamp)}
              </p>
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center text-sm ml-2 flex-shrink-0 mt-1">
                👤
              </div>
            )}
          </div>
        ))}

        {/* Thinking indicator */}
        {thinking && (
          <div className="flex justify-start">
            <div className="w-8 h-8 rounded-full bg-blue-700 flex items-center justify-center text-sm mr-2 flex-shrink-0">
              🤖
            </div>
            <div className="bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex gap-1 items-center h-4">
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input area ── */}
      <div className="mt-4 flex gap-2 items-end">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about microservices, Terraform, Kubernetes… (Enter to send)"
          rows={2}
          className="flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-200 resize-none focus:outline-none focus:border-blue-600"
        />
        <button
          onClick={sendMessage}
          disabled={thinking || !input.trim()}
          className="px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-sm font-medium transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
}
