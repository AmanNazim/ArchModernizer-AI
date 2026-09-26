"use client";

import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useJobStore } from "@/store/jobStore";
import type { MicroserviceBlueprint } from "@/store/jobStore";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Skeleton ───────────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="animate-pulse bg-gray-800 rounded-xl p-5 space-y-3 border border-gray-700">
      <div className="h-5 bg-gray-700 rounded w-2/5" />
      <div className="h-3 bg-gray-700 rounded w-4/5" />
      <div className="h-3 bg-gray-700 rounded w-3/5" />
      <div className="flex gap-2 pt-1">
        <div className="h-5 bg-gray-700 rounded w-24" />
        <div className="h-5 bg-gray-700 rounded w-20" />
      </div>
      <div className="h-28 bg-gray-700 rounded-lg w-full mt-2" />
    </div>
  );
}

// ── Code block with copy button ────────────────────────────────────────────

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="rounded-lg overflow-hidden border border-gray-700">
      <div className="flex items-center justify-between bg-gray-800 px-4 py-2">
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
          {language}
        </span>
        <button
          onClick={handleCopy}
          className="text-xs text-gray-400 hover:text-white transition-colors"
        >
          {copied ? "Copied!" : "Copy to Clipboard"}
        </button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={vscDarkPlus}
        customStyle={{ margin: 0, borderRadius: 0, fontSize: "0.75rem" }}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}

// ── Blueprint card ─────────────────────────────────────────────────────────

function BlueprintCard({ blueprint }: { blueprint: MicroserviceBlueprint }) {
  const [expanded, setExpanded] = useState(false);

  const codeLanguage = blueprint.language ?? "yaml";

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full text-left px-5 py-4 flex items-start justify-between gap-4 hover:bg-gray-750 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white text-sm truncate">
            {blueprint.service_name}
          </h3>
          <p className="text-gray-400 text-xs mt-1 line-clamp-2">
            {blueprint.description}
          </p>
        </div>
        <span className="text-gray-500 text-lg leading-none mt-0.5 flex-shrink-0">
          {expanded ? "−" : "+"}
        </span>
      </button>

      {expanded && (
        <div className="px-5 pb-5 space-y-4 border-t border-gray-700">
          {blueprint.original_files_referenced.length > 0 && (
            <div className="pt-4">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                Referenced Files
              </p>
              <div className="flex flex-wrap gap-2">
                {blueprint.original_files_referenced.map((file) => (
                  <span
                    key={file}
                    className="font-mono text-xs bg-gray-900 text-green-400 border border-gray-700 rounded px-2 py-0.5"
                  >
                    {file}
                  </span>
                ))}
              </div>
            </div>
          )}

          {blueprint.openapi_spec && (
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                OpenAPI Spec
              </p>
              <CodeBlock code={blueprint.openapi_spec} language="yaml" />
            </div>
          )}

          {blueprint.code_snippet && (
            <div>
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
                Code Snippet
              </p>
              <CodeBlock code={blueprint.code_snippet} language={codeLanguage} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function CodeModernizer() {
  const job_id = useJobStore((s) => s.job_id);
  const job_status = useJobStore((s) => s.job_status);
  const modernizer_artifacts = useJobStore((s) => s.modernizer_artifacts);
  const setModernizerArtifacts = useJobStore((s) => s.setModernizerArtifacts);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleModernize() {
    if (!job_id) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/api/modernize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Modernize request failed");
      }

      const data: { microservices: MicroserviceBlueprint[] } = await res.json();
      setModernizerArtifacts(data.microservices ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  const isProcessing = job_status === "PROCESSING";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Code Modernizer</h2>
        <p className="text-sm text-gray-400 mt-1">
          Generate microservice blueprints from your ingested repository.
        </p>
      </div>

      {!job_id ? (
        <div className="bg-yellow-950 border border-yellow-800 rounded-xl px-5 py-4 text-yellow-300 text-sm">
          Complete repository ingestion first to unlock the Code Modernizer.
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <button
              onClick={handleModernize}
              disabled={loading || isProcessing}
              className="px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-sm font-medium transition-colors text-white"
            >
              {loading ? "Generating…" : "Generate Blueprints"}
            </button>
            {error && (
              <p className="text-red-400 text-sm bg-red-950 border border-red-800 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
          </div>

          {isProcessing ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          ) : modernizer_artifacts.length === 0 ? (
            <div className="flex items-center justify-center bg-gray-800 border border-dashed border-gray-700 rounded-xl py-16 text-gray-500 text-sm">
              No blueprints generated yet
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {modernizer_artifacts.map((blueprint) => (
                <BlueprintCard key={blueprint.service_name} blueprint={blueprint} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
