import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";

type Company = {
  id: string;
  name: string;
  app_name: string;
  phone_tel: string | null;
  contact_email: string | null;
  is_active: boolean;
};

type FormState = { name: string; app_name: string; phone_tel: string; contact_email: string };

const EMPTY_FORM: FormState = { name: "", app_name: "", phone_tel: "", contact_email: "" };

const API = "http://localhost:8080/api";

export function CompaniesTab() {
  const { user } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${user!.token}`, "Content-Type": "application/json" };

  async function load() {
    const res = await fetch(`${API}/admin/companies`, { headers });
    if (res.ok) setCompanies(await res.json());
  }

  useEffect(() => { load(); }, []);

  function openAdd() {
    setEditingCompany(null);
    setForm(EMPTY_FORM);
    setError(null);
    setShowModal(true);
  }

  function openEdit(c: Company) {
    setEditingCompany(c);
    setForm({ name: c.name, app_name: c.app_name, phone_tel: c.phone_tel ?? "", contact_email: c.contact_email ?? "" });
    setError(null);
    setShowModal(true);
  }

  function closeModal() {
    setShowModal(false);
    setEditingCompany(null);
    setForm(EMPTY_FORM);
    setError(null);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const method = editingCompany ? "PUT" : "POST";
      const url = editingCompany
        ? `${API}/admin/companies/${editingCompany.id}`
        : `${API}/admin/companies`;

      const phone = form.phone_tel
        ? form.phone_tel.startsWith("tel:") ? form.phone_tel : `tel:${form.phone_tel}`
        : "";

      const res = await fetch(url, {
        method,
        headers,
        body: JSON.stringify({ ...form, phone_tel: phone || null }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Failed to save company");
      }
      await load();
      closeModal();
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
          <button type="button" className="btn-add" onClick={openAdd}>
            + Add Company
          </button>
        </div>
        <div className="admin-panel__table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Company Name</th>
                <th>App Name</th>
                <th>Phone</th>
                <th>Contact Email</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {companies.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--color-text-muted)", padding: "2rem" }}>No companies yet</td></tr>
              )}
              {companies.map((c) => (
                <tr key={c.id}>
                  <td style={{ fontWeight: 500, color: "var(--color-text)" }}>{c.name}</td>
                  <td>{c.app_name || "—"}</td>
                  <td>{c.phone_tel ?? "—"}</td>
                  <td>{c.contact_email ?? "—"}</td>
                  <td>
                    <span className={`status-badge status-badge--${c.is_active ? "active" : "inactive"}`}>
                      {c.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td style={{ display: "flex", gap: "0.5rem" }}>
                    <button type="button" className="tbl-btn" onClick={() => openEdit(c)}>
                      Edit
                    </button>
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
        <div className="modal-backdrop" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal__header">
              <h3>{editingCompany ? "Edit Insurance Company" : "Add Insurance Company"}</h3>
              <button type="button" onClick={closeModal}>×</button>
            </div>
            <div className="modal__body">
              <div className="modal__field">
                <label>Company Name</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Allianz Insurance Lanka Ltd" />
              </div>
              <div className="modal__field">
                <label>App Name <span style={{ color: "var(--color-text-muted)", fontWeight: 400 }}>(shown in mobile app)</span></label>
                <input value={form.app_name} onChange={(e) => setForm({ ...form, app_name: e.target.value })} placeholder="Allianz Insurance" />
              </div>
              <div className="modal__field">
                <label>Phone</label>
                <input value={form.phone_tel} onChange={(e) => setForm({ ...form, phone_tel: e.target.value })} placeholder="tel:+94112303300" />
              </div>
              <div className="modal__field">
                <label>Contact Email</label>
                <input type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} placeholder="admin@company.lk" />
              </div>
              {error && <p className="modal__error">{error}</p>}
            </div>
            <div className="modal__footer">
              <button type="button" className="modal__cancel" onClick={closeModal}>Cancel</button>
              <button type="button" className="modal__save" onClick={handleSave} disabled={saving || !form.name || !form.app_name}>
                {saving ? "Saving…" : editingCompany ? "Save Changes" : "Create Company"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
