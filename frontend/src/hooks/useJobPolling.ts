"use client";

import { useEffect } from "react";
import { useJobStore } from "@/store/jobStore";

export function useJobPolling(job_id: string | null): void {
  const job_status = useJobStore((state) => state.job_status);
  const setJobStatus = useJobStore((state) => state.setJobStatus);

  useEffect(() => {
    if (!job_id) return;
    if (job_status === "COMPLETED" || job_status === "FAILED") return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/api/status/${job_id}`);
        const data = await res.json();
        setJobStatus(data.status);
      } catch {
        setJobStatus("FAILED");
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [job_id, job_status, setJobStatus]);
}
