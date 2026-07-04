import { useEffect, useRef, useState } from "react";

type GaussianSplatViewerProps = {
  url: string;
};

export function GaussianSplatViewer({ url }: GaussianSplatViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const viewerRef = useRef<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || !url) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    import("@mkkellogg/gaussian-splats-3d").then((GS3D) => {
      if (cancelled || !containerRef.current) return;

      const container = containerRef.current;

      const viewer = new GS3D.Viewer({
        rootElement: container,
        cameraUp: [0, 0, 1],
        initialCameraPosition: [0, -5, 3],
        initialCameraLookAt: [0, 0, 0],
        selfDrivenMode: true,
        useBuiltInControls: true,
        halfPrecisionCovariancesOnGPU: false,
        gpuAcceleratedSort: false,
        // SharedArrayBuffer requires Cross-Origin-Isolated headers which we don't set.
        // Setting false makes workers copy memory instead — slightly slower but works.
        sharedMemoryForWorkers: false,
      });

      viewerRef.current = viewer;

      viewer
        .addSplatScene(url, {
          splatAlphaRemovalThreshold: 5,
          showLoadingUI: false,
          // URL has no .ply extension — tell the library the format explicitly.
          // SceneFormat.Ply = 2 in @mkkellogg/gaussian-splats-3d
          format: GS3D.SceneFormat.Ply,
        })
        .then(() => {
          if (!cancelled) {
            setLoading(false);
            viewer.start();
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            console.error("GaussianSplatViewer: failed to load splat:", err);
            setError(String(err));
            setLoading(false);
          }
        });
    }).catch((err: unknown) => {
      if (!cancelled) {
        console.error("GaussianSplatViewer: failed to import library:", err);
        setError(String(err));
        setLoading(false);
      }
    });

    return () => {
      cancelled = true;
      if (viewerRef.current) {
        viewerRef.current.stop?.();
        viewerRef.current.dispose?.();
        viewerRef.current = null;
      }
    };
  }, [url]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative", background: "#e8eaed" }}>
      {/* The GS3D viewer appends its canvas here */}
      <div ref={containerRef} style={{ width: "100%", height: "100%" }} />

      {loading && (
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          gap: 12, pointerEvents: "none",
        }}>
          <div style={{
            width: 36, height: 36, border: "3px solid #d1d5db",
            borderTopColor: "#f97316", borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }} />
          <span style={{ fontSize: "0.8rem", color: "#6b7280" }}>
            Loading 3D model…
          </span>
        </div>
      )}

      {error && (
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
          gap: 8, padding: 24,
        }}>
          <span style={{ fontSize: "0.85rem", color: "#ef4444", fontWeight: 500 }}>
            Failed to render 3D model
          </span>
          <span style={{ fontSize: "0.72rem", color: "#9ca3af", textAlign: "center", maxWidth: 320 }}>
            {error}
          </span>
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
