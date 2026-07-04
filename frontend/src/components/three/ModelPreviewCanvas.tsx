import { Suspense, useMemo } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls, useGLTF } from "@react-three/drei";
import { DamagedCar } from "./CarModels";

function GlbModel({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  // Clone so the same cached scene object isn't shared with CompareViewCanvas
  // (a Three.js Object3D can only belong to one scene graph at a time)
  const cloned = useMemo(() => scene.clone(true), [scene]);
  return <primitive object={cloned} />;
}

function PreviewScene({ glbUrl }: { glbUrl?: string }) {
  return (
    <>
      <color attach="background" args={["#f1f5f9"]} />
      <ambientLight intensity={0.65} />
      <directionalLight position={[5, 8, 4]} intensity={1.1} castShadow />
      {glbUrl ? (
        <GlbModel url={glbUrl} />
      ) : (
        <DamagedCar damaged position={[0, 0, 0]} rotation={[0, -0.35, 0]} />
      )}
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
  glbUrl?: string;
};

export function ModelPreviewCanvas({ onFullscreen, glbUrl }: ModelPreviewCanvasProps) {
  return (
    <div className="model-preview">
      <Canvas
        shadows
        camera={{ position: [4.5, 2.5, 5], fov: 40 }}
        gl={{ antialias: true }}
      >
        <Suspense fallback={null}>
          <PreviewScene glbUrl={glbUrl} />
        </Suspense>
      </Canvas>
      <button type="button" className="model-preview__link" onClick={onFullscreen}>
        &lt;Full screen view&gt;
      </button>
    </div>
  );
}
