import { Navigate, Route, BrowserRouter as Router, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Layout } from "@/components/Layout";
import { DemoWatermark } from "@/components/DemoWatermark";
import { LoginPage } from "@/pages/LoginPage";
import { HomePage } from "@/pages/HomePage";
import { CotacaoPage } from "@/pages/CotacaoPage";
import { HistoricoPage } from "@/pages/HistoricoPage";
import { ComparativoPage } from "@/pages/ComparativoPage";
import { ClientesPage } from "@/pages/ClientesPage";
import { ClienteDetailPage } from "@/pages/ClienteDetailPage";
import { RenovacaoPage } from "@/pages/RenovacaoPage";
import { RelatoriosPage } from "@/pages/RelatoriosPage";

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
      <Route path="/" element={<Navigate to="/home" replace />} />
      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppRoutes />
        <DemoWatermark />
      </AuthProvider>
    </Router>
  );
}
