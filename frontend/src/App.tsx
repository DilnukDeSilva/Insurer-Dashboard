import { useState } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { AdminPage } from "./pages/AdminPage";

function AppRoutes() {
  const { user } = useAuth();
  const [showAdmin, setShowAdmin] = useState(false);

  if (!user) return <LoginPage />;
  if (showAdmin && user.role === "admin") return <AdminPage onBack={() => setShowAdmin(false)} />;

  return <DashboardPage onAdminClick={() => setShowAdmin(true)} />;
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;
