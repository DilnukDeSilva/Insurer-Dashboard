import { useState } from "react";

type MediaViewerPanelProps = {
  title: string;
  urls: string[];
  visible: boolean;
  onClose: () => void;
};

function isVideo(url: string): boolean {
  const path = url.split("?")[0];
  return /\.(mp4|mov|webm|avi|mkv)$/i.test(path);
}

export function MediaViewerPanel({ title, urls, visible, onClose }: MediaViewerPanelProps) {
  const [activeIndex, setActiveIndex] = useState(0);

  if (!visible) return null;

  const activeUrl = urls[activeIndex];

  return (
    <div className="accident-images" role="dialog" aria-label={title}>
      <div className="accident-images__header">
        <h3>{title}</h3>
        <button type="button" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>

      <div className="accident-images__main">
        {isVideo(activeUrl) ? (
          <video
            key={activeUrl}
            src={activeUrl}
            controls
            style={{ maxWidth: "100%", maxHeight: "100%" }}
          />
        ) : (
          <img src={activeUrl} alt={`${title} — item ${activeIndex + 1}`} />
        )}
      </div>

      {urls.length > 1 && (
        <div className="accident-images__thumbs">
          {urls.map((url, i) => (
            <button
              key={url}
              type="button"
              className={i === activeIndex ? "active" : ""}
              onClick={() => setActiveIndex(i)}
            >
              {isVideo(url) ? (
                <span style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", fontSize: "1.5rem" }}>
                  ▶
                </span>
              ) : (
                <img src={url} alt="" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
