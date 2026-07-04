import { useState, useEffect } from "react";

type StepStatus = "pending" | "running" | "done" | "failed";

type Step = {
  key: string;
  label: string;
  status: StepStatus;
  started_at?: number;
  completed_at?: number;
};

type PipelineStepsProps = {
  steps: Step[];
  modelState: "idle" | "generating" | "ready" | "error";
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done")    return <span className="ps-icon ps-icon--done">✓</span>;
  if (status === "running") return <span className="ps-icon ps-icon--running">◉</span>;
  if (status === "failed")  return <span className="ps-icon ps-icon--failed">✕</span>;
  return <span className="ps-icon ps-icon--pending">○</span>;
}

function StepTimer({ step, now }: { step: Step; now: number }) {
  if (step.status === "done" && step.started_at && step.completed_at) {
    const dur = step.completed_at - step.started_at;
    return <span className="ps-step__time ps-step__time--done">{formatDuration(dur)}</span>;
  }
  if (step.status === "running" && step.started_at) {
    const elapsed = now / 1000 - step.started_at;
    return <span className="ps-step__time ps-step__time--running">{formatDuration(elapsed)}</span>;
  }
  if (step.status === "failed" && step.started_at && step.completed_at) {
    const dur = step.completed_at - step.started_at;
    return <span className="ps-step__time ps-step__time--failed">{formatDuration(dur)}</span>;
  }
  return null;
}

export function PipelineSteps({ steps, modelState }: PipelineStepsProps) {
  const [minimized, setMinimized] = useState(false);
  const [now, setNow] = useState(Date.now());

  // Tick every second to update elapsed time for running steps
  useEffect(() => {
    const hasRunning = steps.some((s) => s.status === "running");
    if (!hasRunning) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [steps]);

  if (modelState === "idle") return null;

  const running = steps.find((s) => s.status === "running");
  const doneCount = steps.filter((s) => s.status === "done").length;
  const failed = steps.some((s) => s.status === "failed");

  const headerLabel =
    modelState === "ready"   ? "3D model ready" :
    modelState === "error"   ? "Pipeline failed" :
    running                  ? running.label :
    "Preparing…";

  return (
    <div className={`ps-float ${failed ? "ps-float--error" : modelState === "ready" ? "ps-float--ready" : ""}`}>
      <div className="ps-float__header" onClick={() => setMinimized((v) => !v)}>
        <span className="ps-float__title">
          {modelState === "generating" && <span className="ps-float__dot" />}
          {headerLabel}
        </span>
        <span className="ps-float__meta">
          {steps.length > 0 && `${doneCount}/${steps.length}`}
        </span>
        <button type="button" className="ps-float__toggle" aria-label={minimized ? "Expand" : "Minimise"}>
          {minimized ? "▲" : "▼"}
        </button>
      </div>

      {!minimized && steps.length > 0 && (
        <div className="ps-float__body">
          {steps.map((step) => (
            <div key={step.key} className={`ps-step ps-step--${step.status}`}>
              <StepIcon status={step.status} />
              <span className="ps-step__label">{step.label}</span>
              <StepTimer step={step} now={now} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
