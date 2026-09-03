import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { api, ApiError, setUnauthorizedHandler } from "./api";

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

const REFRESH_INTERVAL_MS = 30 * 60 * 1000; // 30 min

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      sessionStorage.clear();
      sessionStorage.setItem("mk_session_expired", "1");
      setUser(null);
    });
    return () => setUnauthorizedHandler(() => {});
  }, []);

  // Hydrate from /auth/me — authoritative session check with correct user data
  useEffect(() => {
    api.auth
      .me()
      .then((me) => setUser({ nome: me.nome, papel: me.papel }))
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  // Proactively refresh session every 30 min while the tab is open
  useEffect(() => {
    if (!user) return;
    refreshTimer.current = setInterval(() => {
      api.auth.refresh().catch(() => {});
    }, REFRESH_INTERVAL_MS);
    return () => {
      if (refreshTimer.current) clearInterval(refreshTimer.current);
    };
  }, [user]);

  const login = useCallback(async (email: string, senha: string) => {
    const out = await api.auth.login(email, senha);
    setUser({ nome: out.nome, papel: out.papel });
  }, []);

  const logout = useCallback(async () => {
    await api.auth.logout().catch(() => {});
    sessionStorage.clear();
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
