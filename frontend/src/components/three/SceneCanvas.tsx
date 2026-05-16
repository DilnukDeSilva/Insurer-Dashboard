import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, Grid, OrbitControls } from "@react-three/drei";
import { PlaceholderProperty } from "./PlaceholderProperty";
import "./SceneCanvas.css";

function SceneContent() {
  return (
    <>
      <color attach="background" args={["#0f172a"]} />
      <fog attach="fog" args={["#0f172a", 12, 40]} />

      <ambientLight intensity={0.35} />
      <directionalLight
        position={[8, 12, 6]}
        intensity={1.2}
        castShadow
        shadow-mapSize={[1024, 1024]}
      />

      <PlaceholderProperty />

      <Grid
        infiniteGrid
        fadeDistance={30}
        fadeStrength={1}
        cellSize={0.5}
        sectionSize={2}
        sectionColor="#334155"
        cellColor="#1e293b"
      />
      <ContactShadows position={[0, 0.01, 0]} opacity={0.5} scale={12} blur={2} />
      <Environment preset="city" />

      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.05}
        minDistance={4}
        maxDistance={24}
        maxPolarAngle={Math.PI / 2.05}
      />
    </>
  );
}

function SceneFallback() {
  return (
    <mesh>
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial color="#475569" wireframe />
    </mesh>
  );
}

export function SceneCanvas() {
  return (
    <div className="scene-canvas">
      <Canvas
        shadows
        camera={{ position: [6, 5, 8], fov: 45, near: 0.1, far: 100 }}
        gl={{ antialias: true }}
      >
        <Suspense fallback={<SceneFallback />}>
          <SceneContent />
        </Suspense>
      </Canvas>
      <div className="scene-canvas__hint">
        Drag to orbit · Scroll to zoom · OpenMVS mesh loads here
      </div>
    </div>
  );
}
