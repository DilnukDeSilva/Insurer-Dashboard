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
        <h3>Accident Images — {claim.id}</h3>
        <button type="button" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>
      <div className="accident-images__main">
        <img
          src={images[activeIndex]}
          alt={`Accident upload ${activeIndex + 1} for ${claim.id}`}
        />
      </div>
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
    </div>
  );
}
