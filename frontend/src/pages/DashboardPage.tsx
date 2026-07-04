import { useEffect, useMemo, useState } from "react";
import { ClaimDetailPanel } from "../components/dashboard/ClaimDetailPanel";
import { ClaimsListPanel } from "../components/dashboard/ClaimsListPanel";
import { DashboardHeader } from "../components/dashboard/DashboardHeader";
import { fetchClaims } from "../data/claims";
import type { Claim } from "../types/claim";

export function DashboardPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selectedNic, setSelectedNic] = useState<string>("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchClaims()
      .then((data) => {
        setClaims(data);
        if (data.length > 0) setSelectedNic(data[0].nic);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load claims"))
      .finally(() => setLoading(false));
  }, []);

  const selectedClaim = useMemo(
    () => claims.find((c) => c.nic === selectedNic) ?? claims[0],
    [claims, selectedNic],
  );

  return (
    <div className="dashboard">
      <DashboardHeader />
      <p className="dashboard__company">Allianz Insurance Lanka Limited</p>

      {loading && <p style={{ padding: "2rem" }}>Loading claims…</p>}
      {error && <p style={{ padding: "2rem", color: "red" }}>{error}</p>}

      {!loading && !error && (
        <div className="dashboard__content">
          <ClaimsListPanel
            claims={claims}
            selectedNic={selectedNic}
            search={search}
            onSearchChange={setSearch}
            onSelect={setSelectedNic}
          />
          {selectedClaim && (
            <ClaimDetailPanel claim={selectedClaim} key={selectedClaim.nic} />
          )}
        </div>
      )}
    </div>
  );
}
