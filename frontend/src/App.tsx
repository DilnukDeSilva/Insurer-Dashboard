import { useEffect, useState } from "react";
import "./App.css";

type HealthResponse = {
  status: string;
  service: string;
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
        <p className="status">
          API: {health.service} — {health.status}
        </p>
      ) : (
        <p className="status muted">Start the backend to connect the API.</p>
      )}
    </main>
  );
}

export default App;
