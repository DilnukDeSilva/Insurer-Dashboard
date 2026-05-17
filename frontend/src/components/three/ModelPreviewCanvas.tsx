import { Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls } from "@react-three/drei";
import { DamagedCar } from "./CarModels";

function PreviewScene() {
  return (
    <>
      <color attach="background" args={["#f1f5f9"]} />
      <ambientLight intensity={0.65} />
      <directionalLight position={[5, 8, 4]} intensity={1.1} castShadow />
      <DamagedCar damaged position={[0, 0, 0]} rotation={[0, -0.35, 0]} />
      <ContactShadows position={[0, 0, 0]} opacity={0.35} scale={10} blur={1.5} />
      <Environment preset="studio" />
      <OrbitControls
        enableZoom={false}
        enablePan={false}
        autoRotate
        autoRotateSpeed={0.6}
        minPolarAngle={Math.PI / 3}
        maxPolarAngle={Math.PI / 2.2}
      />
    </>
  );
}

type ModelPreviewCanvasProps = {
  onFullscreen?: () => void;
};

export function ModelPreviewCanvas({ onFullscreen }: ModelPreviewCanvasProps) {
  return (
    <div className="model-preview">
      <Canvas
        shadows
        camera={{ position: [4.5, 2.5, 5], fov: 40 }}
        gl={{ antialias: true }}
      >
        <Suspense fallback={null}>
          <PreviewScene />
        </Suspense>
      </Canvas>
      <button type="button" className="model-preview__link" onClick={onFullscreen}>
        &lt;Full screen view&gt;
      </button>
    </div>
  );
}
