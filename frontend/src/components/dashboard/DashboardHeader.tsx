import { useAuth } from "../../context/AuthContext";

type DashboardHeaderProps = {
  onAdminClick?: () => void;
  showBackToDashboard?: boolean;
};

export function DashboardHeader({ onAdminClick, showBackToDashboard }: DashboardHeaderProps) {
  const { user, logout } = useAuth();

  const initials = user?.name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() ?? "??";

  return (
    <header className="dash-header">
      <div className="dash-header__brand">
        <div className="dash-header__logo" aria-hidden>
          <img src="/images/logo.png" alt="KADUNA.LK" className="dash-header__logo-img" />
        </div>
        <h1 className="dash-header__title">Intelligent 3D Accident Claim System</h1>
      </div>

      <div className="dash-header__user">
        {user?.role === "admin" && (
          <button type="button" className="dash-header__admin-btn" onClick={onAdminClick}>
            {showBackToDashboard ? "← Dashboard" : "Admin Panel"}
          </button>
        )}
        <span className={`dash-header__role-badge dash-header__role-badge--${user?.role}`}>
          {user?.role}
        </span>
        <span>Hi {user?.name?.split(" ")[0] ?? ""}!</span>
        <div className="dash-header__avatar" aria-hidden>{initials}</div>
        <button type="button" className="dash-header__logout" onClick={logout}>
          Sign out
        </button>
      </div>
    </header>
  );
}
