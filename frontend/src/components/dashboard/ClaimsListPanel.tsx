import type { Claim } from "../../types/claim";

type ClaimsListPanelProps = {
  claims: Claim[];
  selectedId: string;
  search: string;
  onSearchChange: (value: string) => void;
  onSelect: (id: string) => void;
};

export function ClaimsListPanel({
  claims,
  selectedId,
  search,
  onSearchChange,
  onSelect,
}: ClaimsListPanelProps) {
  const filtered = claims.filter(
    (c) =>
      c.customer.toLowerCase().includes(search.toLowerCase()) ||
      c.id.toLowerCase().includes(search.toLowerCase()) ||
      c.vehicleModel.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <section className="claims-panel">
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
      <p className="claims-panel__sort">Sorted by Date ↑</p>
      <div className="claims-panel__table-wrap">
        <table className="claims-table">
          <thead>
            <tr>
              <th>NIC</th>
              <th>Customer</th>
              <th>Policy ID</th>
              <th>Vehicle Model</th>
              <th>Submitted</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((claim) => (
              <tr
                key={claim.id}
                className={claim.id === selectedId ? "claims-table__row--selected" : ""}
                onClick={() => onSelect(claim.id)}
              >
                <td>{claim.id}</td>
                <td>{claim.customer}</td>
                <td>{claim.policyId}</td>
                <td>{claim.vehicleModel}</td>
                <td className="claims-table__submitted">
                  <span>{claim.submittedDate}</span>
                  <span>{claim.submittedTime}(IST)</span>
                  <span>{claim.location} (GPS)</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
