import { HealthPanel } from "./components/HealthPanel";
import { SceneCanvas } from "./components/three/SceneCanvas";
import { useHealth } from "./hooks/useHealth";
import "./App.css";

function App() {
  const { health, loading, error } = useHealth();

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1>Insurer Dashboard</h1>
          <p>3D property reconstruction viewer</p>
        </div>
      </header>

      <div className="app__body">
        <HealthPanel health={health} loading={loading} error={error} />
        <section className="app__viewer" aria-label="3D viewer">
          <SceneCanvas />
        </section>
      </div>
    </div>
  );
}

export default App;
