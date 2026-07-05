import { useState } from "react";
import type { Claim } from "../../types/claim";

type AccidentImagesPanelProps = {
  claim: Claim;
  visible: boolean;
  onClose: () => void;
};

export function AccidentImagesPanel({ claim, visible, onClose }: AccidentImagesPanelProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  if (!visible) return null;

  const images = claim.accidentImages;

  return (
    <div className="accident-images" role="dialog" aria-label="Accident images">
      <div className="accident-images__header">
        <h3>Accident Images — {claim.nic}</h3>
        <button type="button" onClick={onClose} aria-label="Close">×</button>
      </div>

      <div className="accident-images__body">
        {/* Left: location info */}
        <div className="accident-images__loc">
          <p className="ai-loc__label">Captured Location</p>
          <p className="ai-loc__address">{claim.location || "—"}</p>
          <div className="ai-loc__divider" />
          <p className="ai-loc__label">Date &amp; Time</p>
          <p className="ai-loc__value">
            {[claim.submittedDate, claim.submittedTime ? `${claim.submittedTime} IST` : ""].filter(Boolean).join(" · ")}
          </p>
        </div>

        {/* Right: original image viewer */}
        <div className="accident-images__media">
          <div className="accident-images__main">
            {images.length > 0
              ? <img src={images[activeIndex]} alt={`Accident image ${activeIndex + 1}`} />
              : <p style={{ color: "var(--color-text-placeholder)", fontSize: "0.85rem" }}>No images available</p>
            }
          </div>
          {images.length > 1 && (
            <div className="accident-images__thumbs">
              {images.map((src, i) => (
                <button
                  key={src}
                  type="button"
                  className={i === activeIndex ? "active" : ""}
                  onClick={() => setActiveIndex(i)}
                >
                  <img src={src} alt="" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
