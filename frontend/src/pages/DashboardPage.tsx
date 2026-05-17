import { useMemo, useState } from "react";
import { ClaimDetailPanel } from "../components/dashboard/ClaimDetailPanel";
import { ClaimsListPanel } from "../components/dashboard/ClaimsListPanel";
import { DashboardHeader } from "../components/dashboard/DashboardHeader";
import { DEFAULT_CLAIM_ID, MOCK_CLAIMS } from "../data/claims";

export function DashboardPage() {
  const [selectedId, setSelectedId] = useState(DEFAULT_CLAIM_ID);
  const [search, setSearch] = useState("");

  const selectedClaim = useMemo(
    () => MOCK_CLAIMS.find((c) => c.id === selectedId) ?? MOCK_CLAIMS[0],
    [selectedId],
  );

  return (
    <div className="dashboard">
      <DashboardHeader />
      <p className="dashboard__company">Allianz Insurance Lanka Limited</p>

      <div className="dashboard__content">
        <ClaimsListPanel
          claims={MOCK_CLAIMS}
          selectedId={selectedId}
          search={search}
          onSearchChange={setSearch}
          onSelect={setSelectedId}
        />
        <ClaimDetailPanel claim={selectedClaim} key={selectedClaim.id} />
      </div>
    </div>
  );
}
