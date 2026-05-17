import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  GizmoHelper,
  GizmoViewport,
  Grid,
  OrbitControls,
} from "@react-three/drei";
import { DamagedCar, ReferenceCar } from "./CarModels";
import { ComparisonLines } from "./ComparisonLines";

function CompareScene() {
  return (
    <>
      <color attach="background" args={["#e8eaed"]} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[6, 10, 5]} intensity={1.2} castShadow />

      <DamagedCar damaged position={[-2.2, 0, 0]} rotation={[0, 0.25, 0]} />
      <ReferenceCar position={[2.2, 0, 0]} rotation={[0, -0.25, 0]} />
      <ComparisonLines />

      <Grid
        position={[0, 0, 0]}
        infiniteGrid
        cellSize={0.5}
        sectionSize={2}
        fadeDistance={20}
        cellColor="#d1d5db"
        sectionColor="#9ca3af"
      />
      <ContactShadows position={[0, 0, 0]} opacity={0.4} scale={14} blur={2} />
      <Environment preset="city" />

      <OrbitControls
        enableDamping
        dampingFactor={0.06}
        minDistance={6}
        maxDistance={16}
        target={[0, 0.5, 0]}
      />

      <GizmoHelper alignment="top-right" margin={[56, 56]}>
        <GizmoViewport axisColors={["#ef4444", "#22c55e", "#3b82f6"]} labelColor="#334155" />
      </GizmoHelper>
    </>
  );
}

type CompareViewCanvasProps = {
  minimized?: boolean;
  onToggleMinimize?: () => void;
};

export function CompareViewCanvas({
  minimized = false,
  onToggleMinimize,
}: CompareViewCanvasProps) {
  return (
    <div className={`compare-view ${minimized ? "compare-view--min" : ""}`}>
      <h3 className="compare-view__title">Compare view</h3>
      <div className="compare-view__canvas-wrap">
        <Canvas
          shadows
          camera={{ position: [0, 3.5, 10], fov: 42 }}
          gl={{ antialias: true }}
        >
          <Suspense fallback={null}>
            <CompareScene />
          </Suspense>
        </Canvas>
      </div>
      <button type="button" className="compare-view__link" onClick={onToggleMinimize}>
        {minimized ? "<Expand view>" : "<Minimize view>"}
      </button>
    </div>
  );
}
