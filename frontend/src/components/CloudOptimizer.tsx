"use client";

/**
 * CloudOptimizer – Tab 2
 *
 * Accepts Terraform (.tf) or Kubernetes YAML as a text input or file upload,
 * sends it to POST /api/optimize, and renders the findings as metric cards
 * and a detailed finding list.
 */

import { useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Types ──────────────────────────────────────────────────────────────────

interface OptimizationFinding {
  severity: "critical" | "warning" | "info";
  category: string;
  description: string;
  recommendation: string;
  line_hint?: number;
}

interface OptimizeResponse {
  manifest_type: string;
  total_findings: number;
  critical_count: number;
  warning_count: number;
  info_count: number;
  findings: OptimizationFinding[];
  overall_score: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────

const PLACEHOLDER_MANIFEST = `# Example Terraform with intentional issues
provider "aws" {
  region = "us-east-1"
}

resource "aws_db_instance" "prod_db" {
  engine               = "mysql"
  instance_class       = "t2.micro"
  publicly_accessible  = true
  skip_final_snapshot  = true
  username             = "admin"
  password             = "hunter2"
}

resource "aws_security_group" "allow_all" {
  name = "allow_all"
  ingress {
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
`;

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-red-950 border-red-700 text-red-300",
  warning: "bg-yellow-950 border-yellow-700 text-yellow-300",
  info: "bg-blue-950 border-blue-700 text-blue-300",
};

const SEVERITY_BADGE: Record<string, string> = {
  critical: "bg-red-600 text-white",
  warning: "bg-yellow-500 text-gray-900",
  info: "bg-blue-600 text-white",
};

// ── Component ──────────────────────────────────────────────────────────────

export default function CloudOptimizer() {
  const [manifest, setManifest] = useState(PLACEHOLDER_MANIFEST);
  const [result, setResult] = useState<OptimizeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleOptimize() {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const fd = new FormData();
      const fileInput = fileRef.current;
      if (fileInput?.files?.[0]) {
        fd.append("file", fileInput.files[0]);
      } else {
        fd.append("manifest", manifest);
      }

      const res = await fetch(`${API_BASE}/api/optimize`, {
        method: "POST",
        body: fd,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Optimize request failed");
      }

      const data: OptimizeResponse = await res.json();
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  // Score colour
  const scoreColor =
    result && result.overall_score >= 80
      ? "text-green-400"
      : result && result.overall_score >= 50
      ? "text-yellow-400"
      : "text-red-400";

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div>
        <h2 className="text-lg font-semibold">Cloud Optimizer</h2>
        <p className="text-sm text-gray-400 mt-1">
          Paste a Terraform config or Kubernetes YAML manifest. The analyser
          will flag security risks, cost inefficiencies, and reliability gaps.
        </p>
      </div>

      {/* ── Metric cards (shown after analysis) ── */}
      {result && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            {
              label: "Health Score",
              value: `${result.overall_score}/100`,
              cls: scoreColor,
            },
            {
              label: "Critical",
              value: result.critical_count,
              cls: "text-red-400",
            },
            {
              label: "Warnings",
              value: result.warning_count,
              cls: "text-yellow-400",
            },
            {
              label: "Info",
              value: result.info_count,
              cls: "text-blue-400",
            },
          ].map((card) => (
            <div
              key={card.label}
              className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center"
            >
              <div className={`text-3xl font-bold ${card.cls}`}>
                {card.value}
              </div>
              <div className="text-xs text-gray-500 mt-1 uppercase tracking-wider">
                {card.label}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Input + findings layout ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: Input */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Manifest Input
            </span>
            <label className="cursor-pointer text-xs text-blue-400 hover:underline">
              Upload file
              <input
                ref={fileRef}
                type="file"
                accept=".tf,.yaml,.yml"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files?.[0])
                    setManifest(`[File selected: ${e.target.files[0].name}]`);
                }}
              />
            </label>
          </div>
          <textarea
            value={manifest}
            onChange={(e) => setManifest(e.target.value)}
            rows={20}
            spellCheck={false}
            className="w-full bg-gray-900 border border-gray-700 rounded-lg p-4 text-sm font-mono text-gray-200 resize-none focus:outline-none focus:border-blue-600"
          />
          <button
            onClick={handleOptimize}
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-sm font-medium transition-colors"
          >
            {loading ? "Analysing…" : "☁️ Analyse Manifest"}
          </button>
          {error && (
            <p className="text-red-400 text-sm bg-red-950 border border-red-800 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        {/* Right: Findings */}
        <div className="flex flex-col gap-3">
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            Findings{" "}
            {result && (
              <span className="ml-1 text-gray-500">
                ({result.manifest_type.toUpperCase()} · {result.total_findings} finding
                {result.total_findings !== 1 ? "s" : ""})
              </span>
            )}
          </span>

          {result && result.findings.length > 0 ? (
            <div className="space-y-3 overflow-y-auto max-h-[520px] pr-1">
              {result.findings.map((f, i) => (
                <div
                  key={i}
                  className={`border rounded-lg px-4 py-3 text-sm ${SEVERITY_STYLES[f.severity] ?? "bg-gray-800 border-gray-700 text-gray-300"}`}
                >
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <span
                      className={`text-xs font-semibold px-2 py-0.5 rounded uppercase ${SEVERITY_BADGE[f.severity]}`}
                    >
                      {f.severity}
                    </span>
                    <span className="text-xs text-gray-500 capitalize">
                      {f.category}
                      {f.line_hint ? ` · line ${f.line_hint}` : ""}
                    </span>
                  </div>
                  <p className="font-medium">{f.description}</p>
                  <p className="mt-1 text-xs opacity-75">
                    💡 {f.recommendation}
                  </p>
                </div>
              ))}
            </div>
          ) : result && result.findings.length === 0 ? (
            <div className="flex-1 bg-green-950 border border-green-700 rounded-lg flex items-center justify-center text-green-400 text-sm min-h-[200px]">
              ✅ No issues found — manifest looks clean!
            </div>
          ) : (
            <div className="flex-1 bg-gray-900 border border-dashed border-gray-700 rounded-lg flex items-center justify-center text-gray-600 text-sm min-h-[400px]">
              Analysis findings will appear here
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
