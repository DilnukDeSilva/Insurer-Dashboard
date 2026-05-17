import { useState, type ReactNode } from "react";
import type { Claim } from "../../types/claim";
import { CompareViewCanvas } from "../three/CompareViewCanvas";
import { ModelPreviewCanvas } from "../three/ModelPreviewCanvas";
import { AccidentImagesPanel } from "./AccidentImagesPanel";

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
  const [compareMinimized, setCompareMinimized] = useState(false);

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
          <DetailRow label="Claim ID" value={claim.id} />
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

          <DetailRow label="Drunk Test" value="" action={<ViewButton label="Drunk Test" />} />
          <DetailRow
            label="Driving Licence"
            value=""
            action={<ViewButton label="Driving Licence" />}
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
                <ViewButton label="3rd Party Details" />
              ) : (
                <span className="detail-btn detail-btn--na">Not applicable</span>
              )
            }
          />
        </div>

        <div className="claim-detail__preview">
          <ModelPreviewCanvas />
        </div>
      </div>

      <div className="claim-detail__compare">
        <CompareViewCanvas
          minimized={compareMinimized}
          onToggleMinimize={() => setCompareMinimized((v) => !v)}
        />
      </div>

      <AccidentImagesPanel
        claim={claim}
        visible={showImages}
        onClose={() => setShowImages(false)}
      />
    </section>
  );
}
