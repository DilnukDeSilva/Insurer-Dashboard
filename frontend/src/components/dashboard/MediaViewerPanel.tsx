import { useState } from "react";
import type { AccidentImage, Claim } from "../../types/claim";

type MediaViewerPanelProps = {
  title: string;
  urls: AccidentImage[];
  visible: boolean;
  onClose: () => void;
  claim: Claim;
};

function isVideo(url: string): boolean {
  const path = url.split("?")[0];
  return /\.(mp4|mov|webm|avi|mkv)$/i.test(path);
}

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

export function MediaViewerPanel({ title, urls, visible, onClose }: MediaViewerPanelProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  if (!visible) return null;

  const active = urls[activeIndex];
  const activeUrl = active?.url ?? "";

  return (
    <div className="accident-images" role="dialog" aria-label={title}>
      <div className="accident-images__header">
        <h3>{title}</h3>
        <button type="button" onClick={onClose} aria-label="Close">×</button>
      </div>

      <div className="accident-images__body">
        {/* Left: per-photo location info */}
        <div className="accident-images__loc">
          <p className="ai-loc__label">Photo Location</p>
          <p className="ai-loc__address">{active ? formatCoords(active) : "—"}</p>
          <div className="ai-loc__divider" />
          <p className="ai-loc__label">Photo Timestamp</p>
          <p className="ai-loc__value">{active ? formatCapturedAt(active.captured_at) : "—"}</p>
        </div>

        {/* Right: original media viewer */}
        <div className="accident-images__media">
          <div className="accident-images__main">
            {urls.length > 0 ? (
              isVideo(activeUrl) ? (
                <video key={activeUrl} src={activeUrl} controls style={{ maxWidth: "100%", maxHeight: "100%" }} />
              ) : (
                <img src={activeUrl} alt={`${title} — item ${activeIndex + 1}`} />
              )
            ) : (
              <p style={{ color: "var(--color-text-placeholder)", fontSize: "0.85rem" }}>No media available</p>
            )}
          </div>
          {urls.length > 1 && (
            <div className="accident-images__thumbs">
              {urls.map((img, i) => (
                <button
                  key={img.url}
                  type="button"
                  className={i === activeIndex ? "active" : ""}
                  onClick={() => setActiveIndex(i)}
                >
                  {isVideo(img.url) ? (
                    <span style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", fontSize: "1.5rem" }}>▶</span>
                  ) : (
                    <img src={img.url} alt="" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
