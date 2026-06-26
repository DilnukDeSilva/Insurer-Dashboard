import { useState } from "react";

type StepStatus = "pending" | "running" | "done" | "failed";

type Step = {
  key: string;
  label: string;
  status: StepStatus;
};

type PipelineStepsProps = {
  steps: Step[];
  modelState: "idle" | "generating" | "ready" | "error";
};

function StepIcon({ status }: { status: StepStatus }) {
  if (status === "done")    return <span className="ps-icon ps-icon--done">✓</span>;
  if (status === "running") return <span className="ps-icon ps-icon--running">◉</span>;
  if (status === "failed")  return <span className="ps-icon ps-icon--failed">✕</span>;
  return <span className="ps-icon ps-icon--pending">○</span>;
}

export function PipelineSteps({ steps, modelState }: PipelineStepsProps) {
  const [minimized, setMinimized] = useState(false);

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
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
