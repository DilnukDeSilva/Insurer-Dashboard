import { useEffect, useMemo, useState } from "react";
import { ClaimDetailPanel } from "../components/dashboard/ClaimDetailPanel";
import { ClaimsListPanel } from "../components/dashboard/ClaimsListPanel";
import { DashboardHeader } from "../components/dashboard/DashboardHeader";
import { PipelineSteps } from "../components/dashboard/PipelineSteps";
import { PipelineJobProvider, usePipelineJob } from "../context/PipelineJobContext";
import { useAuth } from "../context/AuthContext";
import { fetchClaims } from "../data/claims";
import type { Claim } from "../types/claim";

function GlobalPipelineWidget() {
  const { activeJob, clearJob } = usePipelineJob();
  if (!activeJob) return null;
  return (
    <PipelineSteps
      steps={activeJob.steps}
      modelState={activeJob.state}
      claimLabel={activeJob.label}
      onDismiss={activeJob.state !== "generating" ? clearJob : undefined}
    />
  );
}

function DashboardInner({ onAdminClick }: { onAdminClick?: () => void }) {
  const { user } = useAuth();
  const [claims, setClaims] = useState<Claim[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchClaims()
      .then((data) => {
        setClaims(data);
        if (data.length > 0) setSelectedFolder(data[0].folder);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load claims"))
      .finally(() => setLoading(false));
  }, []);

  const selectedClaim = useMemo(
    () => claims.find((c) => c.folder === selectedFolder) ?? claims[0],
    [claims, selectedFolder],
  );

  return (
    <div className="dashboard">
      <DashboardHeader onAdminClick={onAdminClick} />
      {user?.company_name && <p className="dashboard__company">{user.company_name}</p>}

      {loading && <p style={{ padding: "2rem" }}>Loading claims…</p>}
      {error && <p style={{ padding: "2rem", color: "red" }}>{error}</p>}

      {!loading && !error && (
        <div className="dashboard__content">
          <ClaimsListPanel
            claims={claims}
            selectedFolder={selectedFolder}
            search={search}
            onSearchChange={setSearch}
            onSelect={setSelectedFolder}
          />
          {selectedClaim && (
            <ClaimDetailPanel claim={selectedClaim} key={selectedClaim.folder} />
          )}
        </div>
      )}

      <GlobalPipelineWidget />
    </div>
  );
}

export function DashboardPage({ onAdminClick }: { onAdminClick?: () => void }) {
  return (
    <PipelineJobProvider>
      <DashboardInner onAdminClick={onAdminClick} />
    </PipelineJobProvider>
  );
}
