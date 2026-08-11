import { useState } from "react";
import { CompaniesTab } from "../components/admin/CompaniesTab";
import { UsersTab } from "../components/admin/UsersTab";
import { DashboardHeader } from "../components/dashboard/DashboardHeader";

type Tab = "companies" | "users";

export function AdminPage({ onBack }: { onBack: () => void }) {
  const [activeTab, setActiveTab] = useState<Tab>("companies");

  return (
    <div className="admin-page">
      <DashboardHeader onAdminClick={onBack} showBackToDashboard />
      <p className="admin-page__company">Admin Panel</p>

      <div className="admin-body">
        <div className="admin-tabs">
          <button
            type="button"
            className={`admin-tab${activeTab === "companies" ? " admin-tab--active" : ""}`}
            onClick={() => setActiveTab("companies")}
          >
            Insurance Companies
          </button>
          <button
            type="button"
            className={`admin-tab${activeTab === "users" ? " admin-tab--active" : ""}`}
            onClick={() => setActiveTab("users")}
          >
            Users
          </button>
        </div>

        {activeTab === "companies" && <CompaniesTab />}
        {activeTab === "users" && <UsersTab />}
      </div>
    </div>
  );
}
