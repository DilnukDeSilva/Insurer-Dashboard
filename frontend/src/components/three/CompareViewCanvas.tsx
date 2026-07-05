import { Suspense, useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  GizmoHelper,
  GizmoViewport,
  Grid,
  OrbitControls,
  useGLTF,
} from "@react-three/drei";
import * as THREE from "three";
import { DamagedCar, ReferenceCar } from "./CarModels";
import { ComparisonLines } from "./ComparisonLines";
import { GaussianSplatViewer } from "./GaussianSplatViewer";

function GeneratedModel({ url }: { url: string }) {
  const { scene } = useGLTF(url);

  // Compute scale + position from the UNROTATED clone so the math is stable.
  // OpenMVS outputs Y-down (camera convention); we correct with a π X-rotation.
  // After that rotation: Y→-Y, Z→-Z, so the original max.y becomes the new floor.
  const { cloned, scale, position } = useMemo(() => {
    const cloned = scene.clone(true);
    const box = new THREE.Box3().setFromObject(cloned);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);

    if (maxDim === 0) {
      return { cloned, scale: 1, position: [0, 0, 0] as [number, number, number] };
    }

    const s = 4 / maxDim;
    return {
      cloned,
      scale: s,
      position: [
        -center.x * s,   // centre on X (unchanged by X-rotation)
        box.max.y * s,   // original bottom (max.y) becomes new floor after flip
        center.z * s,    // Z is negated by X-rotation so offset is +cz
      ] as [number, number, number],
    };
  }, [scene]);

  return (
    <group position={position} scale={scale}>
      <group rotation={[Math.PI, 0, 0]}>
        <primitive object={cloned} castShadow receiveShadow />
      </group>
    </group>
  );
}

function CompareScene({ glbUrl }: { glbUrl?: string }) {
  return (
    <>
      <color attach="background" args={["#e8eaed"]} />
      <ambientLight intensity={0.8} />
      <directionalLight position={[6, 10, 5]} intensity={1.2} castShadow />
      <directionalLight position={[-6, 4, -5]} intensity={0.4} />

      {glbUrl ? (
        <GeneratedModel url={glbUrl} />
      ) : (
        <>
          <DamagedCar damaged position={[-2.2, 0, 0]} rotation={[0, 0.25, 0]} />
          <ReferenceCar position={[2.2, 0, 0]} rotation={[0, -0.25, 0]} />
          <ComparisonLines />
        </>
      )}

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
        minDistance={2}
        maxDistance={20}
        target={[0, 0.5, 0]}
      />

      <GizmoHelper alignment="top-right" margin={[56, 56]}>
        <GizmoViewport axisColors={["#ef4444", "#22c55e", "#3b82f6"]} labelColor="#334155" />
      </GizmoHelper>
    </>
  );
}

type CompareViewCanvasProps = {
  glbUrl?: string;
  splatUrl?: string;
};

function downloadFile(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
}

export function CompareViewCanvas({ glbUrl, splatUrl }: CompareViewCanvasProps) {
  const hasModel = !!(splatUrl || glbUrl);

  return (
    <div className="compare-view">
      <div className="compare-view__header">
        <h3 className="compare-view__title">
          {hasModel ? "Generated 3D Model" : "Compare view"}
        </h3>
        {splatUrl && (
          <button
            type="button"
            className="compare-view__download"
            onClick={() => downloadFile(splatUrl, "model.ply")}
          >
            Download PLY
          </button>
        )}
        {!splatUrl && glbUrl && (
          <button
            type="button"
            className="compare-view__download"
            onClick={() => downloadFile(glbUrl, "model.glb")}
          >
            Download GLB
          </button>
        )}
      </div>
      <div className="compare-view__canvas-wrap">
        {splatUrl ? (
          <GaussianSplatViewer url={splatUrl} />
        ) : glbUrl ? (
          <Canvas
            shadows
            camera={{ position: [0, 3.5, 10], fov: 42 }}
            gl={{ antialias: true }}
          >
            <Suspense fallback={null}>
              <CompareScene glbUrl={glbUrl} />
            </Suspense>
          </Canvas>
        ) : (
          <div className="compare-view__empty">
            <p>No 3D model generated yet.</p>
            <p>Click <strong>Generate 3D Model</strong> to start.</p>
          </div>
        )}
      </div>
    </div>
  );
}
