import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";

type UserRow = {
  id: string;
  email: string;
  name: string;
  role: string;
  company_id: string | null;
  company_name: string | null;
  is_active: boolean;
};

type Company = { id: string; name: string };

const API = "http://localhost:8080/api";

const ROLES = ["admin", "agent", "staff"] as const;

export function UsersTab() {
  const { user } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ email: "", name: "", password: "", role: "staff", company_id: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const headers = { Authorization: `Bearer ${user!.token}`, "Content-Type": "application/json" };

  async function load() {
    const [uRes, cRes] = await Promise.all([
      fetch(`${API}/admin/users`, { headers }),
      fetch(`${API}/admin/companies`, { headers }),
    ]);
    if (uRes.ok) setUsers(await uRes.json());
    if (cRes.ok) setCompanies(await cRes.json());
  }

  useEffect(() => { load(); }, []);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const body = { ...form, company_id: form.company_id || null };
      const res = await fetch(`${API}/admin/users`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Failed to create user");
      }
      await load();
      setShowModal(false);
      setForm({ email: "", name: "", password: "", role: "staff", company_id: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(id: string) {
    await fetch(`${API}/admin/users/${id}`, { method: "PATCH", headers });
    await load();
  }

  return (
    <>
      <div className="admin-panel">
        <div className="admin-panel__toolbar">
          <h2>User Accounts</h2>
          <button type="button" className="btn-add" onClick={() => setShowModal(true)}>
            + Add User
          </button>
        </div>
        <div className="admin-panel__table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Company</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--color-text-muted)", padding: "2rem" }}>No users yet</td></tr>
              )}
              {users.map((u) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 500, color: "var(--color-text)" }}>{u.name}</td>
                  <td>{u.email}</td>
                  <td><span className={`role-badge role-badge--${u.role}`}>{u.role}</span></td>
                  <td>{u.company_name ?? <span style={{ color: "var(--color-text-muted)" }}>—</span>}</td>
                  <td>
                    <span className={`status-badge status-badge--${u.is_active ? "active" : "inactive"}`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td>
                    <button type="button" className="tbl-btn" onClick={() => handleToggle(u.id)}>
                      {u.is_active ? "Deactivate" : "Activate"}
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
              <h3>Add User Account</h3>
              <button type="button" onClick={() => setShowModal(false)}>×</button>
            </div>
            <div className="modal__body">
              <div className="modal__field">
                <label>Full Name</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Jane Silva" />
              </div>
              <div className="modal__field">
                <label>Email</label>
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="jane@company.lk" />
              </div>
              <div className="modal__field">
                <label>Password</label>
                <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="••••••••" />
              </div>
              <div className="modal__field">
                <label>Role</label>
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  {ROLES.map((r) => (
                    <option key={r} value={r}>{r.charAt(0).toUpperCase() + r.slice(1)}</option>
                  ))}
                </select>
              </div>
              <div className="modal__field">
                <label>Company</label>
                <select value={form.company_id} onChange={(e) => setForm({ ...form, company_id: e.target.value })}>
                  <option value="">— None (Admin) —</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>
              {error && <p className="modal__error">{error}</p>}
            </div>
            <div className="modal__footer">
              <button type="button" className="modal__cancel" onClick={() => setShowModal(false)}>Cancel</button>
              <button type="button" className="modal__save" onClick={handleSave} disabled={saving || !form.email || !form.name || !form.password}>
                {saving ? "Saving…" : "Create User"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
