import { useEffect, useState } from "react";
import "./App.css";

type ToolStatus = {
  name: string;
  configured: boolean;
  description: string;
};

type HealthResponse = {
  status: string;
  service: string;
  pipeline: ToolStatus[];
};

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  return (
    <main className="app">
      <h1>Insurer Dashboard</h1>
      <p className="subtitle">Frontend is running.</p>
      {health ? (
        <>
          <p className="status">
            API: {health.service} — {health.status}
          </p>
          <ul className="pipeline">
            {health.pipeline.map((tool) => (
              <li key={tool.name} className={tool.configured ? "ready" : "pending"}>
                <strong>{tool.name}</strong>
                <span>{tool.configured ? "configured" : "not configured"}</span>
                <p>{tool.description}</p>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="status muted">Start the FastAPI backend to connect the API.</p>
      )}
    </main>
  );
}

export default App;
