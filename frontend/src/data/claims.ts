import type { Claim } from "../types/claim";

function getToken(): string {
  try {
    const raw = localStorage.getItem("auth_user");
    if (raw) return (JSON.parse(raw) as { token: string }).token;
  } catch { /* ignore */ }
  return "";
}

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchClaims(): Promise<Claim[]> {
  const res = await fetch("/api/claims", { headers: authHeaders() });
  if (!res.ok) throw new Error(`Failed to load claims: ${res.status}`);
  return res.json() as Promise<Claim[]>;
}
