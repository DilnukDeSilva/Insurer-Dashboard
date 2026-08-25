/** Returns distance in metres between two GPS coordinates (Haversine formula). */
export function distanceMetres(
  lat1: number, lng1: number,
  lat2: number, lng2: number,
): number {
  const R = 6_371_000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`;
}

export type DistanceLevel = "ok" | "warn" | "danger";

export function distanceLevel(m: number): DistanceLevel {
  if (m <= 25) return "ok";
  if (m <= 100) return "warn";
  return "danger";
}
