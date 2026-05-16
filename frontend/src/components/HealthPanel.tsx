import type { HealthResponse } from "../types/api";
import "./HealthPanel.css";

type HealthPanelProps = {
  health: HealthResponse | null;
  loading: boolean;
  error: string | null;
};

export function HealthPanel({ health, loading, error }: HealthPanelProps) {
  if (loading) {
    return (
      <aside className="health-panel">
        <p className="health-panel__muted">Connecting to API…</p>
      </aside>
    );
  }

  if (error || !health) {
    return (
      <aside className="health-panel">
        <h2>Backend</h2>
        <p className="health-panel__muted">
          Start the FastAPI server on port 8000.
        </p>
        {error && <p className="health-panel__error">{error}</p>}
      </aside>
    );
  }

  return (
    <aside className="health-panel">
      <h2>Pipeline</h2>
      <p className="health-panel__status">
        {health.service} — {health.status}
      </p>
      <ul className="health-panel__tools">
        {health.pipeline.map((tool) => (
          <li
            key={tool.name}
            className={
              tool.configured
                ? "health-panel__tool health-panel__tool--ready"
                : "health-panel__tool"
            }
          >
            <div className="health-panel__tool-header">
              <strong>{tool.name}</strong>
              <span>{tool.configured ? "ready" : "pending"}</span>
            </div>
            <p>{tool.description}</p>
          </li>
        ))}
      </ul>
    </aside>
  );
}
