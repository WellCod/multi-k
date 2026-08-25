import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, ApiError } from "./api";

interface AuthUser {
  nome: string;
  papel: string;
}

interface AuthCtx {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, senha: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // Hydrate from /auth/me equivalent — we test by calling a protected endpoint.
  // Simple: try GET /dominios; 200 means we're logged in, 401 means not.
  useEffect(() => {
    api.dominios
      .list()
      .then(() => {
        // We don't have /auth/me yet; store user name from session storage
        const stored = sessionStorage.getItem("mk_user");
        if (stored) setUser(JSON.parse(stored) as AuthUser);
        else setUser({ nome: "Usuário", papel: "corretor" });
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) {
          setUser(null);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, senha: string) => {
    const out = await api.auth.login(email, senha);
    const u = { nome: out.nome, papel: out.papel };
    sessionStorage.setItem("mk_user", JSON.stringify(u));
    setUser(u);
  }, []);

  const logout = useCallback(async () => {
    await api.auth.logout().catch(() => {});
    sessionStorage.clear();
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
