import { useEffect, useState } from "react";
import type { AccidentImage } from "../../types/claim";
import { distanceMetres, formatDistance, distanceLevel } from "../../utils/geo";

type ReferenceLocation = { gps_lat: number | null; gps_lng: number | null };

type AccidentImagesPanelProps = {
  nic: string;
  images: AccidentImage[];
  loading?: boolean;
  visible: boolean;
  onClose: () => void;
  referenceLocation?: ReferenceLocation | null;
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

export function AccidentImagesPanel({ nic, images, loading, visible, onClose, referenceLocation }: AccidentImagesPanelProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => { setActiveIndex(0); }, [images]);

  if (!visible) return null;

  const active = images[activeIndex];

  return (
    <div className="accident-images" role="dialog" aria-label="Accident images">
      <div className="accident-images__header">
        <h3>Accident Images — {nic}</h3>
        <button type="button" onClick={onClose} aria-label="Close">×</button>
      </div>

      <div className="accident-images__body">
        {loading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", flex: 1, color: "var(--color-text-placeholder)", fontSize: "0.85rem" }}>
            Loading images…
          </div>
        ) : (
          <>
            {/* Left: per-photo location info */}
            <div className="accident-images__loc">
              <p className="ai-loc__label">Photo Location</p>
              {active && active.gps_lat != null && active.gps_lng != null ? (
                <a
                  href={`https://www.google.com/maps?q=${active.gps_lat},${active.gps_lng}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ai-loc__coords-btn"
                >
                  {formatCoords(active)}
                </a>
              ) : (
                <p className="ai-loc__address">{active ? formatCoords(active) : "—"}</p>
              )}
              {(() => {
                if (!active || active.gps_lat == null || active.gps_lng == null) return null;
                const ref = referenceLocation;
                if (!ref || ref.gps_lat == null || ref.gps_lng == null) return null;
                const dist = distanceMetres(ref.gps_lat, ref.gps_lng, active.gps_lat, active.gps_lng);
                const level = distanceLevel(dist);
                const icon = level === "ok" ? "✓" : "⚠";
                const label = level === "ok" ? "Location Matched" : `${formatDistance(dist)} from accident site`;
                return (
                  <span className={`ai-loc__dist ai-loc__dist--${level}`}>
                    {icon} {label}
                  </span>
                );
              })()}
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
          </>
        )}
      </div>
    </div>
  );
}
