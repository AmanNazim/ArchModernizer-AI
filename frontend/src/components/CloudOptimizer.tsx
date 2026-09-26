"use client";

import { useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useJobStore } from "@/store/jobStore";
import type { CloudFinding, CloudScanResult } from "@/store/jobStore";

// ── Skeleton ───────────────────────────────────────────────────────────────

function MetricCardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl bg-gray-800 p-5 flex flex-col gap-3">
      <div className="h-3 w-24 rounded bg-gray-700" />
      <div className="h-8 w-12 rounded bg-gray-700" />
    </div>
  );
}

function FindingCardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl bg-gray-800 border border-gray-700 p-5 flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <div className="h-5 w-14 rounded-full bg-gray-700" />
        <div className="h-4 w-32 rounded bg-gray-700" />
      </div>
      <div className="h-4 w-3/4 rounded bg-gray-700" />
      <div className="h-4 w-1/2 rounded bg-gray-700" />
      <div className="h-24 rounded-lg bg-gray-700" />
    </div>
  );
}

function LoadingSkeletons() {
  return (
    <div className="flex flex-col gap-8">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <MetricCardSkeleton key={i} />
        ))}
      </div>
      <div className="flex flex-col gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <FindingCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}

// ── Metric card ────────────────────────────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: number | string;
  accent: string;
}

function MetricCard({ label, value, accent }: MetricCardProps) {
  return (
    <div className="rounded-xl bg-gray-800 border border-gray-700 p-5 flex flex-col gap-1">
      <span className={`text-xs font-semibold uppercase tracking-wider ${accent}`}>
        {label}
      </span>
      <span className="text-3xl font-bold text-white">{value}</span>
    </div>
  );
}

// ── Finding card ───────────────────────────────────────────────────────────

const severityStyles: Record<CloudFinding["severity"], string> = {
  HIGH: "border-red-500 bg-red-50/10",
  MEDIUM: "border-yellow-500 bg-yellow-50/10",
  LOW: "border-blue-500 bg-blue-50/10",
};

const severityTextStyles: Record<CloudFinding["severity"], string> = {
  HIGH: "text-red-400",
  MEDIUM: "text-yellow-400",
  LOW: "text-blue-400",
};

function FindingCard({ finding }: { finding: CloudFinding }) {
  const [copied, setCopied] = useState(false);
  const [showFix, setShowFix] = useState(false);

  function handleCopy() {
    if (!finding.suggested_fix) return;
    navigator.clipboard.writeText(finding.suggested_fix).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div
      className={`rounded-xl border p-5 flex flex-col gap-3 ${severityStyles[finding.severity]}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`text-xs font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border ${severityTextStyles[finding.severity]} border-current`}
        >
          {finding.severity}
        </span>
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wide">
          {finding.category}
        </span>
        <span className="text-sm font-semibold text-white ml-auto">
          {finding.issue_type}
        </span>
      </div>

      <p className="text-sm text-gray-300 leading-relaxed">{finding.description}</p>

      {finding.suggested_fix && (
        <div className="flex flex-col gap-2">
          <button
            onClick={() => setShowFix((v) => !v)}
            className="self-start text-xs font-medium text-gray-400 hover:text-white transition-colors underline underline-offset-2"
          >
            {showFix ? "Hide" : "Show"} Suggested Fix
          </button>

          {showFix && (
            <div className="relative rounded-lg overflow-hidden">
              <button
                onClick={handleCopy}
                className="absolute top-2 right-2 z-10 text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white transition-colors"
              >
                {copied ? "Copied!" : "Copy Fix"}
              </button>
              <SyntaxHighlighter
                language={finding.fix_language ?? "bash"}
                style={vscDarkPlus}
                customStyle={{ margin: 0, borderRadius: "0.5rem", fontSize: "0.8rem" }}
                wrapLongLines
              >
                {finding.suggested_fix}
              </SyntaxHighlighter>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function CloudOptimizer() {
  const job_id = useJobStore((s) => s.job_id);
  const job_status = useJobStore((s) => s.job_status);
  const cloud_artifacts = useJobStore((s) => s.cloud_artifacts);
  const setCloudArtifacts = useJobStore((s) => s.setCloudArtifacts);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!job_id || job_status === "PROCESSING") return;
    if (cloud_artifacts) return;

    setLoading(true);
    setError(null);

    fetch("/api/cloud-optimize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Server responded ${res.status}`);
        return res.json() as Promise<CloudScanResult>;
      })
      .then((data) => {
        setCloudArtifacts(data);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load cloud scan results.");
      })
      .finally(() => setLoading(false));
  }, [job_id, job_status, cloud_artifacts, setCloudArtifacts]);

  // ── Guardrail: no job yet ──────────────────────────────────────────────

  if (!job_id) {
    return (
      <div className="rounded-xl border border-gray-700 bg-gray-800 p-6 text-center text-gray-400 text-sm">
        Complete repository ingestion first to unlock Cloud Optimizer.
      </div>
    );
  }

  // ── Guardrail: job still processing ───────────────────────────────────

  if (job_status === "PROCESSING" || loading) {
    return <LoadingSkeletons />;
  }

  // ── Error state ────────────────────────────────────────────────────────

  if (error) {
    return (
      <div className="rounded-xl border border-red-700 bg-red-900/20 p-6 text-center text-red-400 text-sm">
        {error}
      </div>
    );
  }

  // ── No data yet ────────────────────────────────────────────────────────

  if (!cloud_artifacts) return null;

  const { security_count, cost_count, performance_count, health_score, findings } =
    cloud_artifacts;

  const healthColor =
    health_score >= 80
      ? "text-green-400"
      : health_score >= 50
      ? "text-yellow-400"
      : "text-red-400";

  return (
    <div className="flex flex-col gap-8">
      {/* Metric cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard label="Security" value={security_count} accent="text-red-400" />
        <MetricCard label="Cost" value={cost_count} accent="text-yellow-400" />
        <MetricCard label="Performance" value={performance_count} accent="text-blue-400" />
        <MetricCard
          label="Health Score"
          value={`${health_score}%`}
          accent={healthColor}
        />
      </div>

      {/* Vulnerability feed */}
      {findings.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-8">
          No findings — your cloud configuration looks clean.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {findings.map((finding) => (
            <FindingCard key={finding.id} finding={finding} />
          ))}
        </div>
      )}
    </div>
  );
}
