import { useState } from "react";
import type { Claim } from "../../types/claim";

type ClaimsListPanelProps = {
  claims: Claim[];
  selectedFolder: string;
  search: string;
  onSearchChange: (value: string) => void;
  onSelect: (folder: string) => void;
  expanded?: boolean;
};

export function ClaimsListPanel({
  claims,
  selectedFolder,
  search,
  onSearchChange,
  onSelect,
  expanded,
}: ClaimsListPanelProps) {
  const [sortAsc, setSortAsc] = useState(false);

  const filtered = claims
    .filter(
      (c) =>
        c.customer.toLowerCase().includes(search.toLowerCase()) ||
        c.nic.toLowerCase().includes(search.toLowerCase()) ||
        c.vehicleModel.toLowerCase().includes(search.toLowerCase()),
    )
    .sort((a, b) => {
      const da = a.submittedDate ? new Date(a.submittedDate).getTime() : 0;
      const db = b.submittedDate ? new Date(b.submittedDate).getTime() : 0;
      return sortAsc ? da - db : db - da;
    });

  return (
    <section className={`claims-panel${expanded ? " claims-panel--slim" : ""}`}>
      {!expanded && (
        <div className="claims-panel__toolbar">
          <h2>Claims awaiting review</h2>
          <div className="claims-panel__search">
            <input
              type="search"
              placeholder="Search by Name"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              aria-label="Search claims"
            />
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <circle cx="11" cy="11" r="7" stroke="#9ca3af" strokeWidth="2" />
              <path d="M20 20l-3-3" stroke="#9ca3af" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>
        </div>
      )}
      <button
        type="button"
        className="claims-panel__sort"
        onClick={() => setSortAsc((v) => !v)}
      >
        {expanded ? (sortAsc ? "↑" : "↓") : `Sorted by Date ${sortAsc ? "↑" : "↓"}`}
      </button>
      <div className="claims-panel__table-wrap">
        <table className="claims-table">
          <thead>
            <tr>
              {/* Full columns — hidden in slim mode */}
              {!expanded && <th>NIC</th>}
              <th>Customer</th>
              {/* <th>Policy ID</th> */}
              {!expanded && <th>Vehicle Model</th>}
              <th>Submitted</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((claim) => (
              <tr
                key={claim.folder}
                className={claim.folder === selectedFolder ? "claims-table__row--selected" : ""}
                onClick={() => onSelect(claim.folder)}
              >
                {!expanded && <td>{claim.nic}</td>}
                <td>{claim.customer}</td>
                {/* <td>{claim.policyId}</td> */}
                {!expanded && <td>{claim.vehicleModel}</td>}
                <td>{claim.submittedDate || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
