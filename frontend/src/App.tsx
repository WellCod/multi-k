import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Layout } from "@/components/Layout";
import { LoginPage } from "@/pages/LoginPage";
import { CotacaoPage } from "@/pages/CotacaoPage";
import { HistoricoPage } from "@/pages/HistoricoPage";
import { ComparativoPage } from "@/pages/ComparativoPage";
import { ClienteDetailPage } from "@/pages/ClienteDetailPage";
import { RenovacaoPage } from "@/pages/RenovacaoPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
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
      <Route path="*" element={<Navigate to="/cotacao" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </Router>
  );
}
