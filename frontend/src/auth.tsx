import { createContext, ReactNode, useContext, useState } from "react";
import { api } from "./api";
import type { Role, User } from "./types";

interface AuthState {
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  register: (email: string, password: string, role: Role) => Promise<User>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>(null!);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem("qd_user");
    return raw ? JSON.parse(raw) : null;
  });

  async function handleToken(res: { access_token: string; user: User }) {
    localStorage.setItem("qd_token", res.access_token);
    localStorage.setItem("qd_user", JSON.stringify(res.user));
    setUser(res.user);
    return res.user;
  }

  const login = (email: string, password: string) =>
    api<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }).then(handleToken);

  const register = (email: string, password: string, role: Role) =>
    api<{ access_token: string; user: User }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, role }),
    }).then(handleToken);

  const logout = () => {
    localStorage.removeItem("qd_token");
    localStorage.removeItem("qd_user");
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, login, register, logout }}>{children}</AuthContext.Provider>;
}
