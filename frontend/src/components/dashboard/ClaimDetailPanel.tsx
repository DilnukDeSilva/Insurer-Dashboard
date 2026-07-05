import { useState, useEffect, useRef } from "react";
import type { Claim } from "../../types/claim";
import { CompareViewCanvas } from "../three/CompareViewCanvas";
import { AccidentImagesPanel } from "./AccidentImagesPanel";
import { MediaViewerPanel } from "./MediaViewerPanel";
import { PipelineSteps } from "./PipelineSteps";

const API = "http://localhost:8080/api";

type ModelState = "idle" | "generating" | "ready" | "error";
type Step = { key: string; label: string; status: "pending" | "running" | "done" | "failed" };
type SavedModel = { job_id: string; created_at: string };

function InfoRow({
  label,
  value,
  passed,
}: {
  label: string;
  value?: string;
  passed?: boolean;
}) {
  return (
    <div className="irow">
      <span className="irow__label">{label}</span>
      <span className="irow__value">{value ?? ""}</span>
      {passed !== undefined && (
        <span className={passed ? "badge--pass" : "badge--fail"}>
          {passed ? "✓  Passed" : "✗  Failed"}
        </span>
      )}
    </div>
  );
}

export function ClaimDetailPanel({ claim }: { claim: Claim }) {
  const [showImages, setShowImages] = useState(false);
  const [showUserVerification, setShowUserVerification] = useState(false);
  const [showThirdParty, setShowThirdParty] = useState(false);
  const [showLocation, setShowLocation] = useState(false);

  const [modelState, setModelState] = useState<ModelState>("idle");
  const [splatUrl, setSplatUrl] = useState<string | undefined>(undefined);
  const [steps, setSteps] = useState<Step[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [existingModels, setExistingModels] = useState<SavedModel[]>([]);
  const [showModelPicker, setShowModelPicker] = useState(false);

  const fetchModels = (nic: string) =>
    fetch(`${API}/claims/${encodeURIComponent(nic)}/models`)
      .then((r) => (r.ok ? r.json() : []))
      .then((models: SavedModel[]) => setExistingModels(models))
      .catch(() => {});

  useEffect(() => {
    setModelState("idle");
    setSplatUrl(undefined);
    setSteps([]);
    setExistingModels([]);
    setShowModelPicker(false);
    if (pollRef.current) clearInterval(pollRef.current);
    fetchModels(claim.nic);
  }, [claim.nic]);

  async function handleGenerateModel() {
    setModelState("generating");
    setSplatUrl(undefined);
    setSteps([
      { key: "download", label: "Downloading images",             status: "pending" },
      { key: "colmap",   label: "Structure from Motion (COLMAP)", status: "pending" },
      { key: "train",    label: "Training Gaussian Splat",         status: "pending" },
      { key: "export",   label: "Exporting splat model",          status: "pending" },
    ]);

    try {
      const createRes = await fetch(`${API}/pipeline/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nic: claim.nic, customer_name: claim.customer }),
      });
      if (!createRes.ok) throw new Error("Failed to create pipeline job");
      const { job_id } = await createRes.json();

      await fetch(`${API}/pipeline/jobs/${job_id}/run?background=true&skip_zero_dce=true`, {
        method: "POST",
      });

      pollRef.current = setInterval(async () => {
        const statusRes = await fetch(`${API}/pipeline/jobs/${job_id}/status`);
        if (!statusRes.ok) return;
        const data = await statusRes.json();
        setSteps(data.steps ?? []);

        if (data.overall === "completed") {
          clearInterval(pollRef.current!);
          setSplatUrl(`${API}/pipeline/jobs/${job_id}/splat`);
          setModelState("ready");
          fetchModels(claim.nic);
        } else if (data.overall === "failed") {
          clearInterval(pollRef.current!);
          setModelState("error");
        }
      }, 4000);
    } catch {
      setModelState("error");
    }
  }

  const dateLine =
    [
      claim.submittedDate,
      claim.submittedTime ? `${claim.submittedTime}(IST)` : "",
      claim.location ? `${claim.location} (GPS)` : "",
    ]
      .filter(Boolean)
      .join(" ");

  return (
    <section className="claim-detail">
      {/* ── Top info section ──────────────────────────────── */}
      <div className="claim-info">
        {/* Detail rows + action buttons side by side */}
        <div className="claim-body">
          {/* Left: field rows */}
          <div className="claim-rows">
            <InfoRow label="NIC" value={claim.nic} passed={true} />
            <InfoRow label="Customer" value={claim.customer} passed={true} />
            <InfoRow label="Policy ID" value={claim.policyId} passed={true} />
            <InfoRow label="Vehicle Model" value={claim.vehicleModel} passed={true} />
            <InfoRow label="Vehicle Reg No" value={claim.vehicleRegNo ?? "CBQ - 6899"} passed={true} />
          </div>

          {/* Center: view buttons */}
          <div className="claim-views">
            {claim.userVerificationAvailable ? (
              <button
                type="button"
                className="action-view"
                onClick={() => setShowUserVerification(true)}
              >
                <span>User Verification Test</span>
                <span className="action-view__arrow">View &gt;</span>
              </button>
            ) : (
              <button type="button" className="action-view action-view--disabled" disabled>
                <span>User Verification Test</span>
                <span className="action-view__arrow action-view__arrow--na">N/A</span>
              </button>
            )}

            <button
              type="button"
              className="action-view"
              onClick={() => setShowImages(true)}
            >
              <span>Accident Images</span>
              <span className="action-view__arrow">View &gt;</span>
            </button>

            {claim.thirdPartyApplicable ? (
              <button
                type="button"
                className="action-view"
                onClick={() => setShowThirdParty(true)}
              >
                <span>3rd Party Details</span>
                <span className="action-view__arrow">View &gt;</span>
              </button>
            ) : (
              <button type="button" className="action-view action-view--disabled" disabled>
                <span>3rd Party Details</span>
                <span className="action-view__arrow action-view__arrow--na">N/A</span>
              </button>
            )}

            <button
              type="button"
              className="action-view"
              onClick={() => setShowLocation(true)}
            >
              <span>Location Details</span>
              <span className="action-view__arrow">View &gt;</span>
            </button>
          </div>

          {/* Right: action buttons */}
          <div className="claim-btns">
            <button type="button" className="btn-approve">Approve</button>
            <button type="button" className="btn-inspect">Require Inspection</button>

            {existingModels.length > 0 && modelState !== "generating" && (
              <button type="button" className="btn-approve" onClick={() => setShowModelPicker(true)}>
                View 3D Model
              </button>
            )}
            {modelState === "idle" && (
              <button type="button" className="btn-inspect" onClick={handleGenerateModel}>
                {existingModels.length > 0 ? "Generate New Model" : "Generate 3D Model"}
              </button>
            )}
            {modelState === "generating" && (
              <span className="model-generating">Generating…</span>
            )}
            {modelState === "error" && (
              <button type="button" className="btn-inspect" onClick={handleGenerateModel}>
                Retry 3D Model
              </button>
            )}
          </div>
        </div>

      </div>

      {/* ── 3D canvas ─────────────────────────────────────── */}
      <div className="claim-detail__compare">
        <CompareViewCanvas splatUrl={splatUrl} />
      </div>

      {/* ── Pipeline progress floating panel (keep as-is) ── */}
      <PipelineSteps steps={steps} modelState={modelState} />

      {/* ── Overlays ──────────────────────────────────────── */}
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
        claim={claim}
      />
      <MediaViewerPanel
        title="3rd Party Details"
        urls={claim.thirdPartyPhotos}
        visible={showThirdParty}
        onClose={() => setShowThirdParty(false)}
        claim={claim}
      />

      {/* ── Model picker overlay ──────────────────────────── */}
      {showModelPicker && (
        <div className="model-picker">
          <div className="model-picker__header">
            <h3>Select 3D Model</h3>
            <button type="button" onClick={() => setShowModelPicker(false)} aria-label="Close">×</button>
          </div>
          <div className="model-picker__list">
            {existingModels.map((m, i) => (
              <button
                key={m.job_id}
                type="button"
                className={`model-picker__item${splatUrl?.includes(m.job_id) ? " model-picker__item--active" : ""}`}
                onClick={() => {
                  setSplatUrl(`${API}/pipeline/jobs/${m.job_id}/splat`);
                  setModelState("ready");
                  setShowModelPicker(false);
                }}
              >
                <span className="model-picker__num">Model {existingModels.length - i}</span>
                <span className="model-picker__date">
                  {m.created_at ? new Date(m.created_at).toLocaleString() : "Unknown date"}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Location Details overlay ───────────────────────── */}
      {showLocation && (
        <div className="accident-images">
          <div className="accident-images__header">
            <h3>Location Details</h3>
            <button type="button" onClick={() => setShowLocation(false)}>×</button>
          </div>
          <div className="location-details">
            <div className="location-row">
              <span className="location-row__label">Reported</span>
              <span className="location-row__value">{dateLine}</span>
            </div>
            <div className="location-row">
              <span className="location-row__label">Captured</span>
              <span className="location-row__value">{dateLine}</span>
            </div>
            <div className="location-row">
              <span className="location-row__label">Submitted</span>
              <span className="location-row__value">{dateLine}</span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
