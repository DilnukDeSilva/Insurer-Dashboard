import { Edges } from "@react-three/drei";

type CarProps = {
  damaged?: boolean;
  position?: [number, number, number];
  rotation?: [number, number, number];
};

function Wheel({ position }: { position: [number, number, number] }) {
  return (
    <mesh position={position} castShadow>
      <cylinderGeometry args={[0.32, 0.32, 0.22, 16]} />
      <meshStandardMaterial color="#1e293b" roughness={0.9} />
    </mesh>
  );
}

export function DamagedCar({
  damaged = true,
  position = [0, 0, 0],
  rotation = [0, 0, 0],
}: CarProps) {
  return (
    <group position={position} rotation={rotation}>
      <mesh position={[0, 0.55, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.9, 0.55, 4.2]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.35} metalness={0.15} />
        {damaged && <Edges color="#22c55e" threshold={15} />}
      </mesh>

      <mesh position={[0, 0.95, -0.15]} castShadow>
        <boxGeometry args={[1.65, 0.55, 2.2]} />
        <meshStandardMaterial color="#e2e8f0" roughness={0.4} />
        <Edges color="#3b82f6" threshold={15} />
      </mesh>

      <mesh position={[0, 0.35, 2.05]} castShadow>
        <boxGeometry args={[1.75, 0.45, 0.35]} />
        <meshStandardMaterial color="#cbd5e1" roughness={0.5} />
      </mesh>

      {damaged && (
        <group position={[-0.55, 0.45, 1.85]} rotation={[0, 0.35, -0.25]}>
          <mesh castShadow>
            <boxGeometry args={[0.7, 0.5, 0.9]} />
            <meshStandardMaterial color="#94a3b8" roughness={0.8} />
            <Edges color="#a855f7" threshold={10} />
          </mesh>
          <mesh position={[0.1, -0.15, 0.35]} rotation={[0.4, 0, 0]}>
            <boxGeometry args={[0.85, 0.25, 0.5]} />
            <meshStandardMaterial color="#64748b" roughness={0.9} />
          </mesh>
        </group>
      )}

      <Wheel position={[-0.85, 0.32, 1.25]} />
      <Wheel position={[0.85, 0.32, 1.25]} />
      <Wheel position={[-0.85, 0.32, -1.25]} />
      <Wheel position={[0.85, 0.32, -1.25]} />
    </group>
  );
}

export function ReferenceCar({
  position = [0, 0, 0],
  rotation = [0, 0, 0],
}: CarProps) {
  return (
    <group position={position} rotation={rotation}>
      <mesh position={[0, 0.55, 0]} castShadow receiveShadow>
        <boxGeometry args={[1.9, 0.55, 4.2]} />
        <meshStandardMaterial color="#334155" roughness={0.4} metalness={0.2} />
      </mesh>

      <mesh position={[0, 0.95, -0.15]} castShadow>
        <boxGeometry args={[1.65, 0.55, 2.2]} />
        <meshStandardMaterial color="#475569" roughness={0.45} />
      </mesh>

      <mesh position={[0, 0.35, 2.05]} castShadow>
        <boxGeometry args={[1.75, 0.45, 0.35]} />
        <meshStandardMaterial color="#1e293b" roughness={0.5} />
      </mesh>

      <Wheel position={[-0.85, 0.32, 1.25]} />
      <Wheel position={[0.85, 0.32, 1.25]} />
      <Wheel position={[-0.85, 0.32, -1.25]} />
      <Wheel position={[0.85, 0.32, -1.25]} />
    </group>
  );
}

/** Anchor points for compare-view measurement lines */
export const DAMAGED_ANCHORS: [number, number, number][] = [
  [-0.5, 0.7, 1.9],
  [-0.3, 0.5, 1.6],
  [0, 0.9, 0.5],
  [0.4, 0.6, -0.8],
  [-0.6, 0.4, -1.2],
];

export const REFERENCE_ANCHORS: [number, number, number][] = [
  [-0.5, 0.7, 1.9],
  [-0.3, 0.5, 1.6],
  [0, 0.9, 0.5],
  [0.4, 0.6, -0.8],
  [-0.6, 0.4, -1.2],
];
