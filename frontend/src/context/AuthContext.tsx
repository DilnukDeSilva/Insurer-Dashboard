import { createContext, useContext, useEffect, useState } from "react";

export type UserRole = "admin" | "agent" | "staff";

export type AuthUser = {
  email: string;
  name: string;
  role: UserRole;
  company_id: string | null;
  company_name: string | null;
  token: string;
};

type AuthContextValue = {
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const STORAGE_KEY = "auth_user";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as AuthUser) : null;
    } catch {
      return null;
    }
  });

  async function login(email: string, password: string) {
    const res = await fetch("http://localhost:8080/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail ?? "Login failed");
    }
    const data = await res.json() as {
      access_token: string;
      name: string;
      role: UserRole;
      company_id: string | null;
      company_name: string | null;
    };
    const authUser: AuthUser = {
      email,
      name: data.name,
      role: data.role,
      company_id: data.company_id,
      company_name: data.company_name ?? null,
      token: data.access_token,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(authUser));
    setUser(authUser);
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
