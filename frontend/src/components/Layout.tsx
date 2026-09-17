import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Home, Plus, History, Users, CalendarClock, BarChart3, FileText, Percent, ShieldCheck, UserCog, Menu, X, Sun, Moon, LogOut, BriefcaseBusiness, Settings2, Layers, ChevronDown } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { api, type RenovacaoCount } from "@/lib/api";
import { useDarkMode } from "@/lib/use-dark-mode";
import { cn } from "@/lib/utils";
import { Page } from "@/components/primitives";

const GROUPS = [
  { label: "Operação", icon: Layers, items: [
    { to: "/home", label: "Início", icon: Home, admin: false },
    { to: "/cotacao", label: "Nova cotação", icon: Plus, admin: false },
    { to: "/historico", label: "Histórico", icon: History, admin: false },
    { to: "/clientes", label: "Clientes", icon: Users, admin: false },
    { to: "/renovacoes", label: "Renovações", icon: CalendarClock, admin: false },
  ] },
  { label: "Gestão", icon: BriefcaseBusiness, items: [
    { to: "/dashboard", label: "Dashboard", icon: BarChart3, admin: false },
    { to: "/relatorios", label: "Relatórios", icon: FileText, admin: false },
    { to: "/comissoes", label: "Comissões", icon: Percent, admin: true },
  ] },
  { label: "Administração", icon: Settings2, items: [
    { to: "/usuarios", label: "Usuários", icon: UserCog, admin: true },
    { to: "/auditoria", label: "Auditoria", icon: ShieldCheck, admin: true },
  ] },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { dark, toggle } = useDarkMode();
  const [sidebarHovered, setSidebarHovered] = useState(false);
  const [sidebarKeyboardFocus, setSidebarKeyboardFocus] = useState(false);
  const collapsed = !sidebarHovered && !sidebarKeyboardFocus;
  const [closedGroups, setClosedGroups] = useState<string[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const drawer = useRef<HTMLDialogElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const [renovCount, setRenovCount] = useState<RenovacaoCount | null>(null);
  const [isStaging, setIsStaging] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    if (!user) return;
    let disposed = false;
    api.renovacoes.count().then(value => { if (!disposed) setRenovCount(value); }).catch(() => undefined);
    api.health().then(h => { if (!disposed) // Só "production" tira o aviso: valor desconhecido é tratado como staging.
        setIsStaging(h.justos_env !== "production"); }).catch(() => undefined);
    return () => { disposed = true; };
  }, [user]);

  useEffect(() => { setMenuOpen(false); }, [pathname]);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1024px)");
    const closeOnDesktop = () => { if (media.matches) setMenuOpen(false); };
    media.addEventListener("change", closeOnDesktop);
    return () => media.removeEventListener("change", closeOnDesktop);
  }, []);
  useEffect(() => {
    if (!menuOpen) return;
    const element = drawer.current;
    const trigger = menuButton.current;
    element?.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      element?.close();
      document.body.style.overflow = overflow;
      trigger?.focus();
    };
  }, [menuOpen]);

  const groups = GROUPS.map(group => ({ ...group, items: group.items.filter(item => !item.admin || user?.papel === "admin") })).filter(group => group.items.length);
  const active = (to: string) => pathname === to || pathname.startsWith(to + "/") || (to === "/historico" && pathname.startsWith("/cotacoes/"));
  const context = pathname.startsWith("/cotacoes/") ? "Comparativo" : groups.flatMap(group => group.items).find(item => active(item.to))?.label ?? "multi-K";
  const handleLogout = async () => {
    if (loggingOut) return;
    setLoggingOut(true);
    setLogoutError(null);
    try {
      await logout();
      navigate("/login");
    } catch {
      setLogoutError("Não foi possível confirmar a saída. Verifique sua conexão e tente novamente.");
    } finally {
      setLoggingOut(false);
    }
  };

  function navigation(compact: boolean) {
    return <nav aria-label="Navegação principal" className="space-y-4 p-3">
      {groups.map(group => {
        const GroupIcon = group.icon;
        const open = !closedGroups.includes(group.label);
        return <section key={group.label} aria-label={group.label}>
        <h2 className="mb-2">
          <button type="button" aria-expanded={open} aria-label={group.label} title={compact ? group.label : undefined}
            onClick={() => setClosedGroups(old => open ? [...old, group.label] : old.filter(label => label !== group.label))}
            className="flex min-h-10 w-full items-center gap-2 rounded-lg border border-line bg-canvas px-2 py-2 text-sm font-semibold text-ink hover:text-action whitespace-nowrap">
            <GroupIcon size={18} aria-hidden="true" className="shrink-0" />
            <span className={compact ? "sr-only" : "flex-1 text-left"}>{group.label}</span>
            {!compact && <ChevronDown size={16} aria-hidden="true" className={cn("shrink-0 transition-transform motion-reduce:transition-none", !open && "-rotate-90")} />}
          </button>
        </h2>
        <ul hidden={!open} className={cn("space-y-1", !compact && "ml-4 border-l border-line pl-2")}>{group.items.map(({ to, label, icon: Icon }) => <li key={to}>
          <Link to={to} onClick={() => setMenuOpen(false)} aria-current={active(to) ? "page" : undefined}
            title={compact ? label : undefined} aria-label={compact ? label : undefined}
            className={cn("flex min-h-10 items-center gap-3 rounded-lg px-2 py-2 text-sm whitespace-nowrap transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-action", active(to) ? "bg-selected text-action font-semibold" : "text-muted hover:bg-canvas hover:text-ink")}>
            <Icon size={18} aria-hidden="true" className="shrink-0" />
            <span className={compact ? "sr-only" : "flex-1"}>{label}</span>
            {to === "/renovacoes" && !!renovCount?.D30 && <span className={compact ? "sr-only" : "text-xs text-warning font-semibold"} aria-label={renovCount.D30 + " renovações em 30 dias"}>{renovCount.D30 > 99 ? "99+" : renovCount.D30}</span>}
          </Link>
        </li>)}</ul>
      </section>; })}
    </nav>;
  }

  return <div className="min-h-screen bg-canvas text-ink">
    <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-surface focus:p-3">Ir para o conteúdo</a>
    <aside onMouseEnter={() => setSidebarHovered(true)} onMouseLeave={() => setSidebarHovered(false)}
      onFocusCapture={event => { if (event.target.matches(":focus-visible")) setSidebarKeyboardFocus(true); }}
      onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget)) setSidebarKeyboardFocus(false); }}
      onPointerDown={() => setSidebarKeyboardFocus(false)}
      className={cn("hidden lg:flex fixed inset-y-0 left-0 z-30 flex-col overflow-hidden border-r border-line bg-surface transition-[width] duration-200 motion-reduce:transition-none", collapsed ? "w-16" : "w-56 shadow-lg")}>
      <Link to="/home" aria-label="multi-K — Início" className="flex h-16 shrink-0 items-center justify-center border-b border-line font-semibold text-lg">{collapsed ? "K" : "multi-K"}</Link>
      <div className="flex-1 overflow-y-auto">{navigation(collapsed)}</div>
    </aside>
    <div className="min-h-screen flex flex-col lg:pl-16">
      <header className="sticky top-0 z-20 border-b border-line bg-surface">
        <div className="flex h-16 items-center justify-between gap-3 px-4 lg:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <button ref={menuButton} onClick={() => setMenuOpen(true)} aria-label="Abrir menu" aria-expanded={menuOpen} aria-controls="mobile-navigation" className="lg:hidden p-2 rounded hover:bg-canvas"><Menu size={20} /></button>
            <span className="truncate text-sm font-medium">{context}</span>
            {isStaging && <span title="Ambiente de staging Justos — preços não refletem produção" className="rounded border border-line bg-canvas px-2 py-1 text-xs font-semibold text-warning">STAGING</span>}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button onClick={toggle} aria-label={dark ? "Mudar para modo claro" : "Mudar para modo escuro"} title={dark ? "Mudar para modo claro" : "Mudar para modo escuro"} className="rounded p-2 text-muted hover:bg-canvas">{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
            <details className="relative">
              <summary className="cursor-pointer list-none rounded px-3 py-2 text-sm hover:bg-canvas"><span className="hidden sm:inline">{user?.nome ?? "Minha conta"}</span><span className="sm:hidden">Conta</span><span aria-hidden="true" className="ml-2 text-muted">▾</span></summary>
              <div className="absolute right-0 mt-2 w-56 rounded-lg border border-line bg-surface p-2 shadow-lg">
                <p className="px-3 py-2 text-sm break-words text-muted">{user?.nome}</p>
                <button onClick={handleLogout} disabled={loggingOut} className="flex w-full items-center gap-2 rounded px-3 py-2 text-sm hover:bg-canvas disabled:opacity-50"><LogOut size={16} />{loggingOut ? "Saindo…" : "Sair"}</button>
                {logoutError && <p role="alert" className="px-3 py-2 text-sm text-danger">{logoutError}</p>}
              </div>
            </details>
          </div>
        </div>
      </header>
      <main id="main-content" tabIndex={-1} className="flex-1 min-w-0 w-full"><Page>{children}</Page></main>
      <footer className="mt-auto border-t border-line px-4 py-3 text-xs text-muted flex flex-wrap justify-between gap-2"><span>multi-K{import.meta.env.VITE_APP_ORG ? ` — ${import.meta.env.VITE_APP_ORG}` : ""}</span><span>v{import.meta.env.VITE_APP_VERSION ?? "0.1.0"}</span></footer>
    </div>
    {menuOpen && <dialog ref={drawer} id="mobile-navigation" aria-label="Menu de navegação" onCancel={() => setMenuOpen(false)} onClick={event => { if (event.target === event.currentTarget) setMenuOpen(false); }}
      className="fixed inset-y-0 left-0 right-auto m-0 h-[100dvh] max-h-none w-72 max-w-[85vw] border-0 bg-surface text-ink p-0 backdrop:bg-black/40">
      <div className="min-h-full flex flex-col" onClick={event => event.stopPropagation()}>
        <div className="flex h-16 items-center justify-between border-b border-line px-4"><span className="text-lg font-semibold">multi-K</span><button autoFocus onClick={() => setMenuOpen(false)} aria-label="Fechar menu" className="p-2 rounded hover:bg-canvas"><X size={20} /></button></div>
        {navigation(false)}
      </div>
    </dialog>}
  </div>;
}
