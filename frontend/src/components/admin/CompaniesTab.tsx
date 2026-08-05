import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";

type Company = {
  id: string;
  name: string;
  code: string;
  contact_email: string | null;
  is_active: boolean;
};

const API = "http://localhost:8080/api";

export function CompaniesTab() {
  const { user } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: "", code: "", contact_email: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${user!.token}`, "Content-Type": "application/json" };

  async function load() {
    const res = await fetch(`${API}/admin/companies`, { headers });
    if (res.ok) setCompanies(await res.json());
  }

  useEffect(() => { load(); }, []);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API}/admin/companies`, {
        method: "POST",
        headers,
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Failed to create company");
      }
      await load();
      setShowModal(false);
      setForm({ name: "", code: "", contact_email: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(id: string) {
    await fetch(`${API}/admin/companies/${id}`, { method: "PATCH", headers });
    await load();
  }

  return (
    <>
      <div className="admin-panel">
        <div className="admin-panel__toolbar">
          <h2>Insurance Companies</h2>
          <button type="button" className="btn-add" onClick={() => setShowModal(true)}>
            + Add Company
          </button>
        </div>
        <div className="admin-panel__table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Code</th>
                <th>Contact Email</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {companies.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: "center", color: "var(--color-text-muted)", padding: "2rem" }}>No companies yet</td></tr>
              )}
              {companies.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 500, color: "var(--color-text)" }}>{c.name}</td>
                  <td><span style={{ fontFamily: "monospace", fontSize: "0.82rem" }}>{c.code}</span></td>
                  <td>{c.contact_email ?? "—"}</td>
                  <td>
                    <span className={`status-badge status-badge--${c.is_active ? "active" : "inactive"}`}>
                      {c.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td>
                    <button type="button" className="tbl-btn" onClick={() => handleToggle(c.id)}>
                      {c.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {showModal && (
        <div className="modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal__header">
              <h3>Add Insurance Company</h3>
              <button type="button" onClick={() => setShowModal(false)}>×</button>
            </div>
            <div className="modal__body">
              <div className="modal__field">
                <label>Company Name</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Allianz Insurance Lanka" />
              </div>
              <div className="modal__field">
                <label>Code</label>
                <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })} placeholder="ALZ" maxLength={10} />
              </div>
              <div className="modal__field">
                <label>Contact Email</label>
                <input type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} placeholder="admin@company.lk" />
              </div>
              {error && <p className="modal__error">{error}</p>}
            </div>
            <div className="modal__footer">
              <button type="button" className="modal__cancel" onClick={() => setShowModal(false)}>Cancel</button>
              <button type="button" className="modal__save" onClick={handleSave} disabled={saving || !form.name || !form.code}>
                {saving ? "Saving…" : "Create Company"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
