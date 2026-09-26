"use client";

import { useRef, useState } from "react";
import { useJobStore } from "@/store/jobStore";
import { useJobPolling } from "@/hooks/useJobPolling";

export default function IngestionPanel() {
  const job_id = useJobStore((state) => state.job_id);
  const setJobId = useJobStore((state) => state.setJobId);
  const setJobStatus = useJobStore((state) => state.setJobStatus);

  useJobPolling(job_id);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ZIP upload state
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // GitHub import state
  const [repoUrl, setRepoUrl] = useState("");

  // --- ZIP handlers ---
  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(true);
  }

  function handleDragLeave() {
    setDragOver(false);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0] ?? null;
    if (file) setZipFile(file);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (file) setZipFile(file);
  }

  async function handleZipIngest() {
    if (!zipFile) return;
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", zipFile);
      const res = await fetch("http://127.0.0.1:8000/api/ingest/zip", {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data: { job_id: string } = await res.json();
      setJobId(data.job_id);
      setJobStatus("PENDING");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setLoading(false);
    }
  }

  // --- GitHub handlers ---
  async function handleGitHubIngest() {
    if (!repoUrl.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("http://127.0.0.1:8000/api/ingest/github", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl.trim() }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data: { job_id: string } = await res.json();
      setJobId(data.job_id);
      setJobStatus("PENDING");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Full-overlay loading spinner */}
      {loading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/80">
          <svg
            className="animate-spin h-10 w-10 text-white"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
        </div>
      )}

      <div className="flex flex-col gap-6">
        {/* Success banner */}
        {job_id && !error && (
          <div className="rounded-lg bg-green-900/40 border border-green-700 px-4 py-3 text-green-300 text-sm">
            Repository ingested! Job ID:{" "}
            <span className="font-mono font-semibold">{job_id}</span> —
            monitoring status…
          </div>
        )}

        {/* Two-column card layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left card — ZIP upload */}
          <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 flex flex-col gap-4">
            <h2 className="text-white font-semibold text-base">
              Upload ZIP Archive
            </h2>

            {/* Drag-and-drop zone */}
            <div
              className={`flex flex-col items-center justify-center min-h-[160px] rounded-xl border-2 border-dashed bg-gray-900 cursor-pointer transition-colors ${
                dragOver ? "border-blue-500" : "border-gray-700"
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              {zipFile ? (
                <span className="text-gray-300 text-sm px-4 text-center break-all">
                  {zipFile.name}
                </span>
              ) : (
                <span className="text-gray-500 text-sm text-center px-4">
                  Drag &amp; drop a <span className="font-mono">.zip</span> file
                  here, or click to browse
                </span>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                className="hidden"
                onChange={handleFileChange}
              />
            </div>

            <button
              onClick={handleZipIngest}
              disabled={!zipFile || loading}
              className="w-full rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium py-2 px-4 transition-colors"
            >
              Upload &amp; Ingest
            </button>
          </div>

          {/* Right card — GitHub import */}
          <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 flex flex-col gap-4">
            <h2 className="text-white font-semibold text-base">
              Import from GitHub
            </h2>

            <input
              type="text"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              placeholder="https://github.com/user/repo"
              className="w-full rounded-lg bg-gray-800 border border-gray-700 text-gray-200 placeholder-gray-500 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />

            <button
              onClick={handleGitHubIngest}
              disabled={!repoUrl.trim() || loading}
              className="w-full rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium py-2 px-4 transition-colors"
            >
              Clone &amp; Ingest
            </button>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="rounded-lg bg-red-900/40 border border-red-700 px-4 py-3 text-red-300 text-sm">
            {error}
          </div>
        )}
      </div>
    </>
  );
}
