import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/cotacao", label: "Nova cotação" },
  { to: "/historico", label: "Histórico" },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 h-12 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="font-semibold text-gray-900 text-sm">multi-K</span>
            <nav className="flex gap-1">
              {NAV.map(({ to, label }) => (
                <Link
                  key={to}
                  to={to}
                  className={cn(
                    "px-3 py-1.5 rounded text-sm transition-colors",
                    pathname.startsWith(to)
                      ? "bg-blue-50 text-blue-700 font-medium"
                      : "text-gray-600 hover:text-gray-900 hover:bg-gray-100",
                  )}
                >
                  {label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500">{user?.nome}</span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              Sair
            </Button>
          </div>
        </div>
      </header>
      <main className="flex-1 mx-auto max-w-6xl w-full px-4 py-6">{children}</main>
    </div>
  );
}
