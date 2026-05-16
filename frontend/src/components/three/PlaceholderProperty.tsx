/**
 * Placeholder geometry until OpenMVS mesh exports are loaded into the scene.
 */
export function PlaceholderProperty() {
  return (
    <group position={[0, 0.5, 0]}>
      <mesh castShadow receiveShadow position={[0, 1.25, 0]}>
        <boxGeometry args={[4, 2.5, 3]} />
        <meshStandardMaterial color="#94a3b8" roughness={0.6} metalness={0.1} />
      </mesh>
      <mesh castShadow receiveShadow position={[0, 0.15, 0]}>
        <boxGeometry args={[5, 0.3, 4]} />
        <meshStandardMaterial color="#64748b" roughness={0.8} />
      </mesh>
    </group>
  );
}
