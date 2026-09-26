"use client";

import { createContext, useContext, useRef, type ReactNode } from "react";
import { createStore } from "zustand/vanilla";
import { useStore } from "zustand/react";
import type { StoreApi } from "zustand/vanilla";

// ── Types ──────────────────────────────────────────────────────────────────

export type JobStatus = "IDLE" | "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface MicroserviceBlueprint {
  service_name: string;
  description: string;
  original_files_referenced: string[];
  openapi_spec?: string;
  code_snippet?: string;
  language?: string;
}

export interface CloudFinding {
  id: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  category: "Security" | "Cost" | "Performance" | "Reliability";
  issue_type: string;
  description: string;
  suggested_fix?: string;
  fix_language?: string;
}

export interface CloudScanResult {
  total_findings: number;
  security_count: number;
  cost_count: number;
  performance_count: number;
  health_score: number;
  findings: CloudFinding[];
}

export interface JobState {
  job_id: string | null;
  job_status: JobStatus;
  active_modules: string[];
  modernizer_artifacts: MicroserviceBlueprint[];
  cloud_artifacts: CloudScanResult | null;
}

export interface JobActions {
  setJobId: (id: string) => void;
  setJobStatus: (s: JobStatus) => void;
  setActiveModules: (m: string[]) => void;
  setModernizerArtifacts: (artifacts: MicroserviceBlueprint[]) => void;
  setCloudArtifacts: (result: CloudScanResult) => void;
  reset: () => void;
}

export type JobStore = JobState & JobActions;

// ── Initial state ──────────────────────────────────────────────────────────

const initialState: JobState = {
  job_id: null,
  job_status: "IDLE",
  active_modules: [],
  modernizer_artifacts: [],
  cloud_artifacts: null,
};

// ── Factory ────────────────────────────────────────────────────────────────

export function createJobStore() {
  return createStore<JobStore>()((set) => ({
    ...initialState,
    setJobId: (id) => set({ job_id: id }),
    setJobStatus: (s) => set({ job_status: s }),
    setActiveModules: (m) => set({ active_modules: m }),
    setModernizerArtifacts: (artifacts) => set({ modernizer_artifacts: artifacts }),
    setCloudArtifacts: (result) => set({ cloud_artifacts: result }),
    reset: () => set(initialState),
  }));
}

// ── Context ────────────────────────────────────────────────────────────────

export const JobStoreContext = createContext<StoreApi<JobStore> | null>(null);

// ── Provider ───────────────────────────────────────────────────────────────

export function JobStoreProvider({ children }: { children: ReactNode }) {
  const storeRef = useRef<StoreApi<JobStore>>(undefined);
  if (!storeRef.current) {
    storeRef.current = createJobStore();
  }
  return (
    <JobStoreContext.Provider value={storeRef.current}>
      {children}
    </JobStoreContext.Provider>
  );
}

// ── Hook ───────────────────────────────────────────────────────────────────

export function useJobStore(): JobStore;
export function useJobStore<U>(selector: (state: JobStore) => U): U;
export function useJobStore<U>(selector?: (state: JobStore) => U): JobStore | U {
  const store = useContext(JobStoreContext);
  if (!store) {
    throw new Error("useJobStore must be used within a JobStoreProvider");
  }
  return useStore(store, selector as (state: JobStore) => U);
}
