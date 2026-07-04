import type { Claim } from "../types/claim";

export async function fetchClaims(): Promise<Claim[]> {
  const res = await fetch("/api/claims");
  if (!res.ok) throw new Error(`Failed to load claims: ${res.status}`);
  return res.json() as Promise<Claim[]>;
}
