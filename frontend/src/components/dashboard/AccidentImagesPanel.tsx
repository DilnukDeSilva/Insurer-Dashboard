import { useState } from "react";
import type { AccidentImage, Claim } from "../../types/claim";

type AccidentImagesPanelProps = {
  claim: Claim;
  visible: boolean;
  onClose: () => void;
};

function formatCapturedAt(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
}

function formatCoords(img: AccidentImage): string {
  if (img.gps_lat != null && img.gps_lng != null) {
    return `${img.gps_lat.toFixed(5)}, ${img.gps_lng.toFixed(5)}`;
  }
  return "—";
}

export function AccidentImagesPanel({ claim, visible, onClose }: AccidentImagesPanelProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  if (!visible) return null;

  const images = claim.accidentImages;
  const active = images[activeIndex];

  return (
    <div className="accident-images" role="dialog" aria-label="Accident images">
      <div className="accident-images__header">
        <h3>Accident Images — {claim.nic}</h3>
        <button type="button" onClick={onClose} aria-label="Close">×</button>
      </div>

      <div className="accident-images__body">
        {/* Left: per-photo location info */}
        <div className="accident-images__loc">
          <p className="ai-loc__label">Photo Location</p>
          <p className="ai-loc__address">{active ? formatCoords(active) : "—"}</p>
          <div className="ai-loc__divider" />
          <p className="ai-loc__label">Photo Timestamp</p>
          <p className="ai-loc__value">
            {active ? formatCapturedAt(active.captured_at) : "—"}
          </p>
        </div>

        {/* Right: original image viewer */}
        <div className="accident-images__media">
          <div className="accident-images__main">
            {images.length > 0
              ? <img src={active?.url} alt={`Accident image ${activeIndex + 1}`} />
              : <p style={{ color: "var(--color-text-placeholder)", fontSize: "0.85rem" }}>No images available</p>
            }
          </div>
          {images.length > 1 && (
            <div className="accident-images__thumbs">
              {images.map((img, i) => (
                <button
                  key={img.url}
                  type="button"
                  className={i === activeIndex ? "active" : ""}
                  onClick={() => setActiveIndex(i)}
                >
                  <img src={img.url} alt="" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
