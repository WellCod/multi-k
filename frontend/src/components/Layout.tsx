import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { api, type RenovacaoCount } from "@/lib/api";
import { useDarkMode } from "@/lib/use-dark-mode";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Page } from "@/components/primitives";

function StagingBadge() {
  return (
    <span
      title="Ambiente de staging Justos — preços não refletem produção"
      className="hidden sm:inline-flex items-center px-2 py-1 rounded text-xs font-bold uppercase tracking-wide bg-canvas text-warning border border-line "
    >
      STAGING
    </span>
  );
}

const NAV_BASE = [
  { to: "/home", label: "Home" },
  { to: "/cotacao", label: "Nova cotação" },
  { to: "/historico", label: "Histórico" },
  { to: "/clientes", label: "Clientes" },
  { to: "/renovacoes", label: "Renovações" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/relatorios", label: "Relatórios" },
];
const NAV_ADMIN = [
  { to: "/auditoria", label: "Auditoria" },
  { to: "/usuarios", label: "Usuários" },
  { to: "/comissoes", label: "Comissões" },
];

const _APP_VERSION = import.meta.env.VITE_APP_VERSION ?? "0.1.0";

function MoonIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function HamburgerIcon({ open }: { open: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {open ? (
        <>
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </>
      ) : (
        <>
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </>
      )}
    </svg>
  );
}

function Breadcrumb({ pathname }: { pathname: string }) {
  const allNav = [...NAV_BASE, ...NAV_ADMIN];
  const current = allNav.find((n) => pathname.startsWith(n.to));
  if (!current || current.to === "/home") return null;
  return (
    <div className="mx-auto max-w-workspace px-4 py-2 flex items-center gap-2 text-xs text-muted border-b border-line bg-surface ">
      <Link to="/home" className="hover:text-muted transition-colors">
        Home
      </Link>
      <span>/</span>
      <span className="text-muted font-medium">{current.label}</span>
    </div>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { dark, toggle } = useDarkMode();
  const [menuOpen, setMenuOpen] = useState(false);
  const [renovCount, setRenovCount] = useState<RenovacaoCount | null>(null);
  const [isStaging, setIsStaging] = useState(false);

  useEffect(() => {
    if (!user) return;
    api.renovacoes.count().then(setRenovCount).catch(() => undefined);
    api.health().then((h) => setIsStaging(h.justos_env === "staging")).catch(() => undefined);
  }, [user]);

  const navItems = [...NAV_BASE, ...(user?.papel === "admin" ? NAV_ADMIN : [])];

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col bg-canvas ">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-line bg-surface ">
        <div className="mx-auto max-w-workspace px-4 h-12 flex items-center justify-between">
          {/* Logo + nav desktop */}
          <div className="flex items-center gap-6">
            <span className="font-semibold text-ink text-sm">multi-K</span>
            {isStaging && <StagingBadge />}
            <nav className="hidden 2xl:flex gap-1" aria-label="Navegação principal">
              {navItems.map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  className={cn(
                    "px-3 py-2 rounded text-sm transition-colors inline-flex items-center gap-1",
                    pathname.startsWith(to)
                      ? "bg-canvas text-action font-medium "
                      : "text-muted hover:text-ink hover:bg-canvas ",
                  )}
                >
                  {label}
                  {to === "/renovacoes" && renovCount && renovCount.D30 > 0 && (
                    <span className="inline-flex items-center justify-center min-w-4 h-4 px-1 text-xs font-bold bg-danger text-ink rounded-full leading-none">
                      {renovCount.D30 > 9 ? "9+" : renovCount.D30}
                    </span>
                  )}
                </Link>
              ))}
            </nav>
          </div>

          {/* Ações direita */}
          <div className="flex items-center gap-2">
            <span className="hidden sm:block text-xs text-muted ">{user?.nome}</span>
            <button
              onClick={toggle}
              title={dark ? "Mudar para modo claro" : "Mudar para modo escuro"}
              aria-label={dark ? "Mudar para modo claro" : "Mudar para modo escuro"}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs text-muted hover:bg-canvas transition-colors border border-line "
            >
              {dark ? <SunIcon /> : <MoonIcon />}
              <span className="hidden sm:inline">{dark ? "Claro" : "Escuro"}</span>
            </button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="hidden 2xl:inline-flex "
            >
              Sair
            </Button>
            {/* Hamburguer — só mobile */}
            <button
              onClick={() => setMenuOpen((v) => !v)}
              aria-label={menuOpen ? "Fechar menu" : "Abrir menu"}
              className="2xl:hidden flex items-center justify-center p-2 rounded text-muted hover:bg-canvas transition-colors"
            >
              <HamburgerIcon open={menuOpen} />
            </button>
          </div>
        </div>

        {/* Drawer mobile */}
        {menuOpen && (
          <div className="2xl:hidden border-t border-line bg-surface px-4 py-3 space-y-1">
            <p className="text-xs text-muted mb-2">{user?.nome}</p>
            {navItems.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                onClick={() => setMenuOpen(false)}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors",
                  pathname.startsWith(to)
                    ? "bg-canvas text-action font-medium "
                    : "text-ink hover:bg-canvas ",
                )}
              >
                {label}
                {to === "/renovacoes" && renovCount && renovCount.D30 > 0 && (
                  <span className="inline-flex items-center justify-center min-w-4 h-4 px-1 text-xs font-bold bg-danger text-ink rounded-full leading-none">
                    {renovCount.D30 > 9 ? "9+" : renovCount.D30}
                  </span>
                )}
              </Link>
            ))}
            <button
              onClick={handleLogout}
              className="block w-full text-left px-3 py-2 rounded text-sm text-danger hover:bg-canvas transition-colors mt-1"
            >
              Sair
            </button>
          </div>
        )}
      </header>

      {/* Breadcrumb */}
      <Breadcrumb pathname={pathname} />

      <main id="main-content" className="flex-1 w-full"><Page>{children}</Page></main>

      {/* Footer */}
      <footer className="border-t border-line bg-surface py-3 mt-auto">
        <div className="mx-auto max-w-workspace px-4 flex items-center justify-between text-xs text-muted ">
          <span>multi-K — Klubi Corretora de Seguros</span>
          <span>v{_APP_VERSION}</span>
        </div>
      </footer>
    </div>
  );
}
