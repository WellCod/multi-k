import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import { DarkModeContext, useDarkModeState } from "@/lib/use-dark-mode";
import { Layout } from "@/components/Layout";
import { LoginPage } from "@/pages/LoginPage";
import { useServerEvents, type ServerEvent } from "@/hooks/useServerEvents";

const HomePage = lazy(() => import("@/pages/HomePage").then((m) => ({ default: m.HomePage })));
const CotacaoPage = lazy(() => import("@/pages/CotacaoPage").then((m) => ({ default: m.CotacaoPage })));
const HistoricoPage = lazy(() => import("@/pages/HistoricoPage").then((m) => ({ default: m.HistoricoPage })));
const ComparativoPage = lazy(() => import("@/pages/ComparativoPage").then((m) => ({ default: m.ComparativoPage })));
const ClientesPage = lazy(() => import("@/pages/ClientesPage").then((m) => ({ default: m.ClientesPage })));
const ClienteDetailPage = lazy(() => import("@/pages/ClienteDetailPage").then((m) => ({ default: m.ClienteDetailPage })));
const RenovacaoPage = lazy(() => import("@/pages/RenovacaoPage").then((m) => ({ default: m.RenovacaoPage })));
const RelatoriosPage = lazy(() => import("@/pages/RelatoriosPage").then((m) => ({ default: m.RelatoriosPage })));
const AuditoriaPage = lazy(() => import("@/pages/AuditoriaPage").then((m) => ({ default: m.AuditoriaPage })));
const UsuariosPage = lazy(() => import("@/pages/UsuariosPage").then((m) => ({ default: m.UsuariosPage })));

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <span className="text-sm text-gray-400 dark:text-gray-500">Carregando…</span>
    </div>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/home"
        element={
          <RequireAuth>
            <Layout>
              <HomePage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/relatorios"
        element={
          <RequireAuth>
            <Layout>
              <RelatoriosPage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/cotacao"
        element={
          <RequireAuth>
            <Layout>
              <CotacaoPage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/historico"
        element={
          <RequireAuth>
            <Layout>
              <HistoricoPage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/cotacoes/:cotacaoId/comparativo"
        element={
          <RequireAuth>
            <Layout>
              <ComparativoPage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/clientes"
        element={
          <RequireAuth>
            <Layout>
              <ClientesPage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/clientes/:clienteId"
        element={
          <RequireAuth>
            <Layout>
              <ClienteDetailPage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/renovacoes"
        element={
          <RequireAuth>
            <Layout>
              <RenovacaoPage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/auditoria"
        element={
          <RequireAuth>
            <Layout>
              <AuditoriaPage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route
        path="/usuarios"
        element={
          <RequireAuth>
            <Layout>
              <UsuariosPage />
            </Layout>
          </RequireAuth>
        }
      />
      <Route path="/" element={<Navigate to="/home" replace />} />
      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
    </Suspense>
  );
}

interface CotacaoToastData {
  id: number;
  cotacao_id: string;
  status: string;
  premio_total: string | null;
}

function CotacaoToasts() {
  const { user } = useAuth();
  const [toasts, setToasts] = useState<CotacaoToastData[]>([]);
  const counterRef = useRef(0);

  const handleEvent = useCallback((event: ServerEvent) => {
    if (event.tipo !== "cotacao.pronta") return;
    const toast: CotacaoToastData = {
      id: ++counterRef.current,
      cotacao_id: String(event.cotacao_id ?? ""),
      status: String(event.status ?? ""),
      premio_total: event.premio_total != null ? String(event.premio_total) : null,
    };
    setToasts((prev) => [...prev.slice(-4), toast]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== toast.id));
    }, 8000);
  }, []);

  useServerEvents(handleEvent, !!user);

  if (toasts.length === 0) return null;

  const statusLabel: Record<string, string> = {
    sucesso: "Cotação aprovada",
    restricao: "Cotação com restrições",
    erro: "Cotação com erros",
  };
  const statusColor: Record<string, string> = {
    sucesso: "bg-green-800 text-green-100",
    restricao: "bg-yellow-800 text-yellow-100",
    erro: "bg-red-800 text-red-100",
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-start gap-3 rounded-lg px-4 py-3 shadow-lg text-sm max-w-xs ${statusColor[t.status] ?? "bg-gray-800 text-gray-100"}`}
        >
          <div className="flex-1">
            <p className="font-medium">{statusLabel[t.status] ?? "Cotação finalizada"}</p>
            {t.premio_total && t.status === "sucesso" && (
              <p className="text-xs opacity-80 mt-0.5">Prêmio: R$ {t.premio_total}</p>
            )}
          </div>
          <button
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            className="opacity-70 hover:opacity-100 leading-none text-lg"
            aria-label="Fechar"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

function OfflineBanner() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  if (online) return null;
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 rounded-lg bg-yellow-800 px-4 py-2 text-sm text-yellow-100 shadow-lg">
      <span className="inline-block h-2 w-2 rounded-full bg-yellow-400" />
      Sem conexão — algumas ações podem falhar
    </div>
  );
}

function DarkModeProvider({ children }: { children: React.ReactNode }) {
  const value = useDarkModeState();
  return (
    <DarkModeContext.Provider value={value}>
      {children}
    </DarkModeContext.Provider>
  );
}

export default function App() {
  return (
    <DarkModeProvider>
      <Router>
        <AuthProvider>
          <AppRoutes />
          <CotacaoToasts />
          <OfflineBanner />
        </AuthProvider>
      </Router>
    </DarkModeProvider>
  );
}
