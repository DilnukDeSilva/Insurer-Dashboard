import { useState, useEffect } from "react";
import type { AccidentImage, Claim, ClaimLocationEntry } from "../../types/claim";
import { useAuth } from "../../context/AuthContext";
import { authHeaders } from "../../data/claims";
import { usePipelineJob } from "../../context/PipelineJobContext";
import { CompareViewCanvas } from "../three/CompareViewCanvas";
import { AccidentImagesPanel } from "./AccidentImagesPanel";
import { MediaViewerPanel } from "./MediaViewerPanel";

const API = "http://localhost:8080/api";

type ModelState = "idle" | "generating" | "ready" | "error" | "low_light";
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
      <div className="irow__header">
        <span className="irow__label">{label}</span>
        <span className="irow__value">{value ?? ""}</span>
      </div>
      {passed !== undefined && (
        <span className={passed ? "badge--pass" : "badge--fail"}>
          {passed ? "✓  Passed" : "✗  Failed"}
        </span>
      )}
    </div>
  );
}

function LocationBlock({
  label,
  sublabel,
  entry,
}: {
  label: string;
  sublabel: string;
  entry?: ClaimLocationEntry;
}) {
  const address = entry?.location_label ?? "—";
  const timestamp = entry?.captured_at_display_local ?? (entry?.captured_at ? new Date(entry.captured_at).toLocaleString() : "—");
  const coords =
    entry?.gps_lat != null && entry?.gps_lng != null
      ? `${entry.gps_lat.toFixed(5)}, ${entry.gps_lng.toFixed(5)}`
      : null;

  return (
    <div className="location-row">
      <div className="location-row__header">
        <span className="location-row__label">{label}</span>
        <span className="location-row__sublabel">{sublabel}</span>
      </div>
      <span className="location-row__value">{address}</span>
      {coords && entry?.gps_lat != null && entry?.gps_lng != null ? (
        <a
          href={`https://www.google.com/maps?q=${entry.gps_lat},${entry.gps_lng}`}
          target="_blank"
          rel="noopener noreferrer"
          className="location-row__coords-link"
        >
          {coords}
        </a>
      ) : null}
      <span className="location-row__time">{timestamp}</span>
    </div>
  );
}

export function ClaimDetailPanel({
  claim,
  expanded = false,
  onToggleExpand,
  isAnimating = false,
}: {
  claim: Claim;
  expanded?: boolean;
  onToggleExpand?: () => void;
  isAnimating?: boolean;
}) {
  const { user } = useAuth();
  const { activeJob, startPolling } = usePipelineJob();
  const isStaff = user?.role === "staff";
  const canApprove = user?.role === "admin" || user?.role === "agent";

  const [showImages, setShowImages] = useState(false);
  const [showUserVerification, setShowUserVerification] = useState(false);
  const [showThirdParty, setShowThirdParty] = useState(false);
  const [showLocation, setShowLocation] = useState(false);
  const [showEnhanced, setShowEnhanced] = useState(false);

  // Local splat URL from existing models (pre-generated); context URL takes precedence when active job matches
  const [localSplatUrl, setLocalSplatUrl] = useState<string | undefined>(undefined);
  const [localEnhancedJobId, setLocalEnhancedJobId] = useState<string | null>(null);
  const [existingModels, setExistingModels] = useState<SavedModel[]>([]);
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [modelsLoading, setModelsLoading] = useState(true);

  // Local error flag for when the job fails to start (before polling begins)
  const [startError, setStartError] = useState(false);
  const [starting, setStarting] = useState(false);

  // Photo data — lazily fetched when the user opens an image panel
  const [photoData, setPhotoData] = useState<{
    walkaround: AccidentImage[];
    user_verification: AccidentImage[];
    third_party: AccidentImage[];
  } | null>(null);
  const [photosLoading, setPhotosLoading] = useState(false);

  const [enhancedPhotos, setEnhancedPhotos] = useState<string[]>([]);
  const [approving, setApproving] = useState(false);
  const [approved, setApproved] = useState(false);
  const [showApproveConfirm, setShowApproveConfirm] = useState(false);

  // Whether the background context job belongs to this claim
  const isActiveJobHere = activeJob?.nic === claim.nic;

  // Derived values — context wins when there's an active job for this claim
  const modelState: ModelState = startError
    ? "error"
    : isActiveJobHere
      ? activeJob!.state
      : localSplatUrl ? "ready" : "idle";

  const splatUrl = (isActiveJobHere && activeJob!.splatUrl) ? activeJob!.splatUrl : localSplatUrl;
  const enhancedJobId = (isActiveJobHere && activeJob!.enhancedJobId) ? activeJob!.enhancedJobId : localEnhancedJobId;

  useEffect(() => {
    setApproved(false);
    setApproving(false);
  }, [claim.folder]);

  async function handleApprove() {
    setApproving(true);
    try {
      const res = await fetch(`${API}/claims/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          nic: claim.nic,
          customer_name: claim.customer,
          folder: claim.folder,
        }),
      });
      if (!res.ok) throw new Error("Failed to approve claim");
      setApproved(true);
    } catch {
      alert("Could not approve this claim. Please try again.");
    } finally {
      setApproving(false);
    }
  }

  const fetchModels = (nic: string) => {
    setModelsLoading(true);
    return fetch(`${API}/claims/${encodeURIComponent(nic)}/models`)
      .then((r) => (r.ok ? r.json() : []))
      .then((models: SavedModel[]) => {
        setExistingModels(models);
        if (models.length > 0) {
          setLocalSplatUrl(`${API}/pipeline/jobs/${models[0].job_id}/splat`);
        }
      })
      .catch(() => {})
      .finally(() => setModelsLoading(false));
  };

  const fetchEnhancedJobs = (nic: string) =>
    fetch(`${API}/claims/${encodeURIComponent(nic)}/enhanced-jobs`)
      .then((r) => (r.ok ? r.json() : []))
      .then((jobs: SavedModel[]) => {
        if (jobs.length > 0) setLocalEnhancedJobId(jobs[0].job_id);
      })
      .catch(() => {});

  async function ensurePhotosLoaded() {
    if (photoData || photosLoading) return;
    setPhotosLoading(true);
    try {
      const res = await fetch(`${API}/claims/${encodeURIComponent(claim.folder)}/photos`, {
        headers: authHeaders(),
      });
      if (res.ok) setPhotoData(await res.json());
    } finally {
      setPhotosLoading(false);
    }
  }

  useEffect(() => {
    setLocalSplatUrl(undefined);
    setLocalEnhancedJobId(null);
    setExistingModels([]);
    setShowModelPicker(false);
    setEnhancedPhotos([]);
    setShowEnhanced(false);
    setStartError(false);
    setPhotoData(null);
    setPhotosLoading(false);
    fetchModels(claim.nic);
    fetchEnhancedJobs(claim.nic);
  }, [claim.nic]);

  async function handleGenerateModel() {
    setStartError(false);
    setStarting(true);
    try {
      const createRes = await fetch(`${API}/pipeline/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nic: claim.nic,
          customer_name: claim.customer,
          folder: claim.folder,
        }),
      });
      if (!createRes.ok) throw new Error("Failed to create pipeline job");
      const { job_id } = await createRes.json();

      await fetch(`${API}/pipeline/jobs/${job_id}/run?background=true&skip_zero_dce=true`, {
        method: "POST",
      });

      // Hand off to the context — polling survives claim switches from here
      startPolling(claim.nic, claim.vehicleRegNo ?? claim.nic, job_id);
    } catch {
      setStartError(true);
    } finally {
      setStarting(false);
    }
  }

  return (
    <section className={`claim-detail${expanded ? " claim-detail--expanded" : ""}${isAnimating ? " claim-detail--animating" : ""}`}>
      {/* ── Top info section ──────────────────────────────── */}
      <div className="claim-info">
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
                onClick={() => { void ensurePhotosLoaded(); setShowUserVerification(true); }}
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
              onClick={() => { void ensurePhotosLoaded(); setShowImages(true); }}
            >
              <span>Accident Images</span>
              <span className="action-view__arrow">View &gt;</span>
            </button>

            {claim.thirdPartyApplicable ? (
              <button
                type="button"
                className="action-view"
                onClick={() => { void ensurePhotosLoaded(); setShowThirdParty(true); }}
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
            {canApprove && (
              <button
                type="button"
                className="btn-approve"
                disabled={approving || approved}
                onClick={() => setShowApproveConfirm(true)}
              >
                {approved ? "Approved ✓" : approving ? "Approving…" : "Approve"}
              </button>
            )}
            {canApprove && (
              <button type="button" className="btn-inspect">Require Inspection</button>
            )}

            {modelState !== "generating" && (
              modelsLoading ? (
                <button type="button" className="btn-approve" disabled>
                  <span className="btn-spinner" />Checking…
                </button>
              ) : existingModels.length > 0 ? (
                <button type="button" className="btn-approve" onClick={() => setShowModelPicker(true)}>
                  View 3D Model
                </button>
              ) : null
            )}
            {!isStaff && (modelState === "idle" || modelState === "ready") && (
              <button
                type="button"
                className="btn-inspect"
                onClick={handleGenerateModel}
                disabled={starting}
              >
                {starting
                  ? <><span className="btn-spinner" />Starting…</>
                  : existingModels.length > 0 ? "Generate New Model" : "Generate 3D Model"
                }
              </button>
            )}
            {!isStaff && modelState === "generating" && (
              <span className="model-generating">Generating…</span>
            )}
            {enhancedJobId && modelState !== "generating" && (
              <button
                type="button"
                className="btn-enhanced"
                onClick={async () => {
                  if (enhancedPhotos.length === 0) {
                    const res = await fetch(`${API}/pipeline/jobs/${enhancedJobId}/enhanced-photos`);
                    if (res.ok) setEnhancedPhotos(await res.json());
                  }
                  setShowEnhanced(true);
                }}
              >
                View Enhanced Photos
              </button>
            )}
            {!isStaff && modelState === "error" && (
              <button type="button" className="btn-inspect" onClick={handleGenerateModel}>
                Retry 3D Model
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── 3D canvas ─────────────────────────────────────── */}
      <div className="claim-detail__compare">
        <CompareViewCanvas
          splatUrl={splatUrl}
          isLoading={modelsLoading}
          expanded={expanded}
          onToggleExpand={onToggleExpand}
          isTransitioning={isAnimating}
        />
      </div>

      {/* ── Overlays ──────────────────────────────────────── */}
      <AccidentImagesPanel
        nic={claim.nic}
        images={photoData?.walkaround ?? []}
        loading={photosLoading}
        visible={showImages}
        onClose={() => setShowImages(false)}
      />
      <MediaViewerPanel
        title="User Verification Test"
        urls={photoData?.user_verification ?? []}
        loading={photosLoading}
        visible={showUserVerification}
        onClose={() => setShowUserVerification(false)}
        claim={claim}
      />
      <MediaViewerPanel
        title="3rd Party Details"
        urls={photoData?.third_party ?? []}
        loading={photosLoading}
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
                  setLocalSplatUrl(`${API}/pipeline/jobs/${m.job_id}/splat`);
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
            <LocationBlock
              label="Reported"
              sublabel=" "
              entry={claim.locations?.insurer_call}
            />
            <LocationBlock
              label="Captured"
              sublabel=" "
              entry={claim.locations?.guided_capture_started}
            />
            <LocationBlock
              label="Submitted"
              sublabel=" "
              entry={claim.locations?.report_submitted}
            />
          </div>
        </div>
      )}

      {/* ── Enhanced Photos overlay (low-light) ───────────── */}
      {showEnhanced && (
        <div className="accident-images">
          <div className="accident-images__header">
            <h3>Enhanced Photos <span className="enhanced-badge">Zero-DCE</span></h3>
            <button type="button" onClick={() => setShowEnhanced(false)}>×</button>
          </div>
          <div className="enhanced-notice">
            Photos were too dark for 3D reconstruction. Zero-DCE neural enhancement has been applied.
          </div>
          {enhancedPhotos.length === 0 ? (
            <div className="enhanced-loading">Loading enhanced photos…</div>
          ) : (
            <div className="enhanced-grid">
              {enhancedPhotos.map((url, i) => (
                <img
                  key={i}
                  src={url}
                  alt={`Enhanced photo ${i + 1}`}
                  className="enhanced-img"
                  onClick={() => window.open(url, "_blank")}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Approve confirmation ──────────────────────────── */}
      {showApproveConfirm && (
        <div className="modal-backdrop" onClick={() => setShowApproveConfirm(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal__header">
              <h3>Confirm Approval</h3>
              <button type="button" onClick={() => setShowApproveConfirm(false)}>×</button>
            </div>
            <div className="modal__body">
              <p style={{ margin: 0, fontSize: "0.95rem", color: "var(--color-text-secondary)", lineHeight: 1.6 }}>
                Are you sure you want to approve the claim for <strong style={{ color: "var(--color-text)" }}>{claim.customer}</strong>?
              </p>
              <p style={{ margin: "0.5rem 0 0", fontSize: "0.82rem", color: "var(--color-text-muted)" }}>
                NIC: {claim.nic}
              </p>
            </div>
            <div className="modal__footer">
              <button type="button" className="modal__cancel" onClick={() => setShowApproveConfirm(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="modal__save"
                disabled={approving}
                onClick={() => { setShowApproveConfirm(false); handleApprove(); }}
              >
                {approving ? "Approving…" : "Yes, Approve"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
