import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { useDarkMode } from "@/lib/use-dark-mode";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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
    <div className="mx-auto max-w-6xl px-4 py-1.5 flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500 border-b border-gray-100 dark:border-gray-700/60 bg-white dark:bg-gray-800">
      <Link to="/home" className="hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
        Home
      </Link>
      <span>/</span>
      <span className="text-gray-600 dark:text-gray-300 font-medium">{current.label}</span>
    </div>
  );
}

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { dark, toggle } = useDarkMode();
  const [menuOpen, setMenuOpen] = useState(false);

  const navItems = [...NAV_BASE, ...(user?.papel === "admin" ? NAV_ADMIN : [])];

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
        <div className="mx-auto max-w-6xl px-4 h-12 flex items-center justify-between">
          {/* Logo + nav desktop */}
          <div className="flex items-center gap-6">
            <span className="font-semibold text-gray-900 dark:text-white text-sm">multi-K</span>
            <nav className="hidden md:flex gap-1" aria-label="Navegação principal">
              {navItems.map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  className={cn(
                    "px-3 py-1.5 rounded text-sm transition-colors",
                    pathname.startsWith(to)
                      ? "bg-blue-50 text-blue-700 font-medium dark:bg-blue-900/30 dark:text-blue-300"
                      : "text-gray-600 hover:text-gray-900 hover:bg-gray-100 dark:text-gray-300 dark:hover:text-white dark:hover:bg-gray-700",
                  )}
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>

          {/* Ações direita */}
          <div className="flex items-center gap-2">
            <span className="hidden sm:block text-xs text-gray-500 dark:text-gray-400">{user?.nome}</span>
            <button
              onClick={toggle}
              title={dark ? "Mudar para modo claro" : "Mudar para modo escuro"}
              aria-label={dark ? "Mudar para modo claro" : "Mudar para modo escuro"}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors border border-gray-200 dark:border-gray-600"
            >
              {dark ? <SunIcon /> : <MoonIcon />}
              <span className="hidden sm:inline">{dark ? "Claro" : "Escuro"}</span>
            </button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="hidden md:inline-flex dark:text-gray-300 dark:hover:text-white dark:hover:bg-gray-700"
            >
              Sair
            </Button>
            {/* Hamburguer — só mobile */}
            <button
              onClick={() => setMenuOpen((v) => !v)}
              aria-label={menuOpen ? "Fechar menu" : "Abrir menu"}
              className="md:hidden flex items-center justify-center p-1.5 rounded text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <HamburgerIcon open={menuOpen} />
            </button>
          </div>
        </div>

        {/* Drawer mobile */}
        {menuOpen && (
          <div className="md:hidden border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 px-4 py-3 space-y-1">
            <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">{user?.nome}</p>
            {navItems.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                onClick={() => setMenuOpen(false)}
                className={cn(
                  "block px-3 py-2 rounded-lg text-sm transition-colors",
                  pathname.startsWith(to)
                    ? "bg-blue-50 text-blue-700 font-medium dark:bg-blue-900/30 dark:text-blue-300"
                    : "text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700",
                )}
              >
                {label}
              </Link>
            ))}
            <button
              onClick={handleLogout}
              className="block w-full text-left px-3 py-2 rounded-lg text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors mt-1"
            >
              Sair
            </button>
          </div>
        )}
      </header>

      {/* Breadcrumb */}
      <Breadcrumb pathname={pathname} />

      <main className="flex-1 mx-auto max-w-6xl w-full px-4 py-6">{children}</main>

      {/* Footer */}
      <footer className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 py-3 mt-auto">
        <div className="mx-auto max-w-6xl px-4 flex items-center justify-between text-xs text-gray-400 dark:text-gray-500">
          <span>multi-K — Klubi Corretora de Seguros</span>
          <span>v{_APP_VERSION}</span>
        </div>
      </footer>
    </div>
  );
}
