import { useState, useEffect, useRef, type ReactNode } from "react";
import type { Claim } from "../../types/claim";
import { CompareViewCanvas } from "../three/CompareViewCanvas";
import { ModelPreviewCanvas } from "../three/ModelPreviewCanvas";
import { AccidentImagesPanel } from "./AccidentImagesPanel";
import { MediaViewerPanel } from "./MediaViewerPanel";
import { PipelineSteps } from "./PipelineSteps";

const API = "http://localhost:8080/api";

type ModelState = "idle" | "generating" | "ready" | "error";

type Step = { key: string; label: string; status: "pending" | "running" | "done" | "failed" };

type ClaimDetailPanelProps = {
  claim: Claim;
};

function DetailRow({
  label,
  value,
  action,
}: {
  label: string;
  value: string;
  action?: ReactNode;
}) {
  return (
    <div className="detail-row">
      <span className="detail-row__label">{label}</span>
      <span className="detail-row__value">{value}</span>
      {action}
    </div>
  );
}

function ViewButton({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <button type="button" className="detail-btn detail-btn--view" onClick={onClick}>
      {label} <span>View &gt;</span>
    </button>
  );
}

export function ClaimDetailPanel({ claim }: ClaimDetailPanelProps) {
  const [showImages, setShowImages] = useState(false);
  const [showUserVerification, setShowUserVerification] = useState(false);
  const [showThirdParty, setShowThirdParty] = useState(false);
  const [compareMinimized, setCompareMinimized] = useState(false);

  const [modelState, setModelState] = useState<ModelState>("idle");
  const [glbUrl, setGlbUrl] = useState<string | undefined>(undefined);
  const [steps, setSteps] = useState<Step[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reset model state when the claim changes
  useEffect(() => {
    setModelState("idle");
    setGlbUrl(undefined);
    setSteps([]);
    if (pollRef.current) clearInterval(pollRef.current);
  }, [claim.nic]);

  async function handleGenerateModel() {
    setModelState("generating");
    setGlbUrl(undefined);
    setSteps([]);

    try {
      // Step 1: create job (downloads images from R2)
      const createRes = await fetch(`${API}/pipeline/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nic: claim.nic, customer_name: claim.customer }),
      });
      if (!createRes.ok) throw new Error("Failed to create pipeline job");
      const { job_id } = await createRes.json();

      // Step 2: trigger the pipeline in background
      await fetch(`${API}/pipeline/jobs/${job_id}/run?background=true&skip_zero_dce=true`, {
        method: "POST",
      });

      // Step 3: poll status every 4 seconds
      pollRef.current = setInterval(async () => {
        const statusRes = await fetch(`${API}/pipeline/jobs/${job_id}/status`);
        if (!statusRes.ok) return;
        const data = await statusRes.json();
        setSteps(data.steps ?? []);

        if (data.overall === "completed") {
          clearInterval(pollRef.current!);
          setGlbUrl(`${API}/pipeline/jobs/${job_id}/model`);
          setModelState("ready");
        } else if (data.overall === "failed") {
          clearInterval(pollRef.current!);
          setModelState("error");
        }
      }, 4000);
    } catch {
      setModelState("error");
    }
  }

  return (
    <section className="claim-detail">
      <div className="claim-detail__top">
        <p className="claim-detail__meta">
          {claim.submittedDate} {claim.submittedTime}(IST) {claim.location} (GPS)
        </p>
        <div className="claim-detail__actions">
          <button type="button" className="btn-approve">
            Approve
          </button>
          <button type="button" className="btn-inspect">
            Require Inspection
          </button>
        </div>
      </div>

      <div className="claim-detail__body">
        <div className="claim-detail__info">
          <DetailRow label="NIC" value={claim.nic} />
          <DetailRow label="Customer" value={claim.customer} />
          <DetailRow label="Policy ID" value={claim.policyId} />
          <DetailRow label="Vehicle Model" value={claim.vehicleModel} />

          <DetailRow
            label="GPS matched"
            value=""
            action={
              <span className="badge badge--pass">
                {claim.gpsMatched ? "Passed" : "Failed"}
              </span>
            }
          />
          <DetailRow
            label="Time stamp signed"
            value=""
            action={
              <span className="badge badge--pass">
                {claim.timestampSigned ? "Passed" : "Failed"}
              </span>
            }
          />

          <DetailRow
            label="User Verification Test"
            value=""
            action={
              claim.userVerificationAvailable ? (
                <ViewButton label="User Verification Test" onClick={() => setShowUserVerification(true)} />
              ) : (
                <span className="detail-btn detail-btn--na">Not available</span>
              )
            }
          />
          <DetailRow
            label="Accident Images"
            value=""
            action={
              <ViewButton label="Accident Images" onClick={() => setShowImages(true)} />
            }
          />
          <DetailRow
            label="3rd Party Details"
            value=""
            action={
              claim.thirdPartyApplicable ? (
                <ViewButton label="3rd Party Details" onClick={() => setShowThirdParty(true)} />
              ) : (
                <span className="detail-btn detail-btn--na">Not applicable</span>
              )
            }
          />
        </div>

        <div className="claim-detail__preview">
          <ModelPreviewCanvas glbUrl={glbUrl} />
          <div className="model-preview__generate">
            {modelState === "idle" && (
              <button
                type="button"
                className="detail-btn detail-btn--view"
                onClick={handleGenerateModel}
              >
                Generate 3D Model
              </button>
            )}
            {modelState === "generating" && (
              <span className="model-preview__status">Generating 3D model…</span>
            )}
            {modelState === "ready" && (
              <span className="model-preview__status model-preview__status--ready">Model ready</span>
            )}
            {modelState === "error" && (
              <button
                type="button"
                className="detail-btn detail-btn--view"
                onClick={handleGenerateModel}
              >
                Retry
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="claim-detail__compare">
        <CompareViewCanvas
          minimized={compareMinimized}
          onToggleMinimize={() => setCompareMinimized((v) => !v)}
          glbUrl={glbUrl}
        />
      </div>

      <PipelineSteps steps={steps} modelState={modelState} />

      <AccidentImagesPanel
        claim={claim}
        visible={showImages}
        onClose={() => setShowImages(false)}
      />
      <MediaViewerPanel
        title="User Verification Test"
        urls={claim.userVerificationPhotos}
        visible={showUserVerification}
        onClose={() => setShowUserVerification(false)}
      />
      <MediaViewerPanel
        title="3rd Party Details"
        urls={claim.thirdPartyPhotos}
        visible={showThirdParty}
        onClose={() => setShowThirdParty(false)}
      />
    </section>
  );
}
