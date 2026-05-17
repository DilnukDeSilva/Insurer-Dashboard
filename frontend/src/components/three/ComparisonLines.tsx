import { Line } from "@react-three/drei";
import type { Vector3Tuple } from "three";
import { DAMAGED_ANCHORS, REFERENCE_ANCHORS } from "./CarModels";

const LINE_COLORS = ["#3b82f6", "#22c55e", "#a855f7", "#eab308", "#ec4899"];

type ComparisonLinesProps = {
  damagedOffset?: Vector3Tuple;
  referenceOffset?: Vector3Tuple;
};

export function ComparisonLines({
  damagedOffset = [-2.2, 0, 0],
  referenceOffset = [2.2, 0, 0],
}: ComparisonLinesProps) {
  return (
    <group>
      {DAMAGED_ANCHORS.map((from, i) => {
        const to = REFERENCE_ANCHORS[i];
        const start: Vector3Tuple = [
          from[0] + damagedOffset[0],
          from[1] + damagedOffset[1],
          from[2] + damagedOffset[2],
        ];
        const end: Vector3Tuple = [
          to[0] + referenceOffset[0],
          to[1] + referenceOffset[1],
          to[2] + referenceOffset[2],
        ];
        return (
          <Line
            key={i}
            points={[start, end]}
            color={LINE_COLORS[i % LINE_COLORS.length]}
            lineWidth={1.5}
            transparent
            opacity={0.85}
          />
        );
      })}
      {DAMAGED_ANCHORS.map((p, i) => (
        <mesh
          key={`d-${i}`}
          position={[
            p[0] + damagedOffset[0],
            p[1] + damagedOffset[1],
            p[2] + damagedOffset[2],
          ]}
        >
          <sphereGeometry args={[0.06, 12, 12]} />
          <meshBasicMaterial color={LINE_COLORS[i % LINE_COLORS.length]} />
        </mesh>
      ))}
      {REFERENCE_ANCHORS.map((p, i) => (
        <mesh
          key={`r-${i}`}
          position={[
            p[0] + referenceOffset[0],
            p[1] + referenceOffset[1],
            p[2] + referenceOffset[2],
          ]}
        >
          <sphereGeometry args={[0.06, 12, 12]} />
          <meshBasicMaterial color={LINE_COLORS[i % LINE_COLORS.length]} />
        </mesh>
      ))}
    </group>
  );
}
