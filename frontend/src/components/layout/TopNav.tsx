"use client";

import { useJobStore } from "@/store/jobStore";
import type { JobStatus } from "@/store/jobStore";

interface TopNavProps {
  title: string;
}

const STATUS_STYLES: Record<JobStatus, string> = {
  IDLE: "bg-gray-700 text-gray-300",
  PENDING: "bg-yellow-900/60 text-yellow-300",
  PROCESSING: "bg-blue-900/60 text-blue-300 animate-pulse",
  COMPLETED: "bg-green-900/60 text-green-300",
  FAILED: "bg-red-900/60 text-red-300",
};

export default function TopNav({ title }: TopNavProps) {
  const jobStatus = useJobStore((s) => s.job_status);
  const jobId = useJobStore((s) => s.job_id);

  const badgeClass = STATUS_STYLES[jobStatus];

  return (
    <header className="flex items-center bg-gray-900 border-b border-gray-800 px-6 py-3">
      {/* Left: page title */}
      <h2 className="text-sm font-semibold text-gray-100 tracking-tight flex-1">
        {title}
      </h2>

      {/* Right: job status badge */}
      <div className="flex items-center gap-2">
        {jobId && (
          <span className="text-xs text-gray-500 font-mono">
            {jobId.slice(0, 8)}
          </span>
        )}
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium ${badgeClass}`}
        >
          {jobStatus}
        </span>
      </div>
    </header>
  );
}
