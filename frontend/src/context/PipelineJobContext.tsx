import { createContext, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

const API = "http://localhost:8080/api";
const SESSION_KEY = "pipeline_active_job";

type StepStatus = "pending" | "running" | "done" | "failed" | "skipped";

export type PipelineStep = {
  key: string;
  label: string;
  status: StepStatus;
  started_at?: number;
  completed_at?: number;
};

export type JobState = "generating" | "ready" | "error" | "low_light";

export type ActiveJob = {
  job_id: string;
  nic: string;
  folder: string;
  label: string;
  steps: PipelineStep[];
  state: JobState;
  splatUrl?: string;
  enhancedJobId?: string;
};

type PipelineJobContextValue = {
  activeJob: ActiveJob | null;
  startPolling: (nic: string, folder: string, label: string, job_id: string) => void;
  clearJob: () => void;
};

const INITIAL_STEPS: PipelineStep[] = [
  { key: "download", label: "Downloading images",         status: "pending" },
  { key: "enhance",  label: "Enhancing image brightness", status: "pending" },
  { key: "colmap",   label: "Mapping camera positions",   status: "pending" },
  { key: "train",    label: "Reconstructing 3D model",    status: "pending" },
  { key: "export",   label: "Exporting 3D model",         status: "pending" },
];

const PipelineJobContext = createContext<PipelineJobContextValue | null>(null);

export function PipelineJobProvider({ children }: { children: ReactNode }) {
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function _stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function _beginInterval(job_id: string) {
    _stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API}/pipeline/jobs/${job_id}/status`);

        // Job lost (backend restarted) — clean up silently
        if (res.status === 404) {
          _stopPolling();
          sessionStorage.removeItem(SESSION_KEY);
          setActiveJob(null);
          return;
        }
        if (!res.ok) return;

        const data = await res.json();

        if (data.overall === "completed") {
          _stopPolling();
          sessionStorage.removeItem(SESSION_KEY);
          setActiveJob((prev) =>
            prev
              ? { ...prev, steps: data.steps ?? prev.steps, state: "ready", splatUrl: `${API}/pipeline/jobs/${job_id}/splat` }
              : null
          );
        } else if (data.overall === "low_light") {
          _stopPolling();
          sessionStorage.removeItem(SESSION_KEY);
          setActiveJob((prev) =>
            prev
              ? { ...prev, steps: data.steps ?? prev.steps, state: "low_light", enhancedJobId: job_id }
              : null
          );
        } else if (data.overall === "failed") {
          _stopPolling();
          sessionStorage.removeItem(SESSION_KEY);
          setActiveJob((prev) =>
            prev ? { ...prev, steps: data.steps ?? prev.steps, state: "error" } : null
          );
        } else {
          setActiveJob((prev) =>
            prev ? { ...prev, steps: data.steps ?? prev.steps } : null
          );
        }
      } catch {
        // ignore transient network errors
      }
    }, 4000);
  }

  // On mount: resume any in-progress job stored from a previous page load
  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (!stored) return;
    let parsed: { job_id: string; nic: string; folder: string; label: string } | null = null;
    try {
      parsed = JSON.parse(stored);
    } catch {
      sessionStorage.removeItem(SESSION_KEY);
      return;
    }
    if (!parsed) return;
    const { job_id, nic, folder, label } = parsed;

    fetch(`${API}/pipeline/jobs/${job_id}/status`)
      .then((r) => {
        if (r.status === 404) { sessionStorage.removeItem(SESSION_KEY); return null; }
        return r.ok ? r.json() : null;
      })
      .then((data) => {
        if (!data) return;
        const overall = data.overall as string;
        if (overall === "running" || overall === "pending") {
          // Job still in progress — restore the popup with live steps
          setActiveJob({
            job_id, nic, folder, label, state: "generating",
            steps: (data.steps ?? INITIAL_STEPS) as PipelineStep[],
          });
          _beginInterval(job_id);
        } else {
          // Already finished while we were away — clear stale entry
          sessionStorage.removeItem(SESSION_KEY);
        }
      })
      .catch(() => sessionStorage.removeItem(SESSION_KEY));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function clearJob() {
    _stopPolling();
    sessionStorage.removeItem(SESSION_KEY);
    setActiveJob(null);
  }

  function startPolling(nic: string, folder: string, label: string, job_id: string) {
    _stopPolling();
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ job_id, nic, folder, label }));
    setActiveJob({ job_id, nic, folder, label, state: "generating", steps: INITIAL_STEPS });
    _beginInterval(job_id);
  }

  return (
    <PipelineJobContext.Provider value={{ activeJob, startPolling, clearJob }}>
      {children}
    </PipelineJobContext.Provider>
  );
}

export function usePipelineJob() {
  const ctx = useContext(PipelineJobContext);
  if (!ctx) throw new Error("usePipelineJob must be used within PipelineJobProvider");
  return ctx;
}
