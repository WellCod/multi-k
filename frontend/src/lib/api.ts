const BASE = import.meta.env.VITE_API_URL ?? "/api";

const _CSRF_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

let _unauthorizedHandler: (() => void) | null = null;

export function setUnauthorizedHandler(fn: () => void): void {
  _unauthorizedHandler = fn;
}

function _getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const csrfHeaders: Record<string, string> = {};
  if (_CSRF_METHODS.has(method)) {
    const token = _getCsrfToken();
    if (token) csrfHeaders["X-CSRF-Token"] = token;
  }

  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...csrfHeaders, ...init?.headers },
    ...init,
  });

  if (res.status === 401) {
    if (_unauthorizedHandler) _unauthorizedHandler();
    throw new ApiError(401, "Não autenticado");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? "Erro inesperado");
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

// ---- Auth ----

export interface LoginOut {
  nome: string;
  papel: string;
}

export interface MeOut {
  id: string;
  nome: string;
  papel: string;
  email: string;
}

export const api = {
  auth: {
    login: (email: string, senha: string) =>
      request<LoginOut>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, senha }),
      }),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
    me: () => request<MeOut>("/auth/me"),
    refresh: () => request<void>("/auth/refresh", { method: "POST" }),
  },

  // ---- Domínios ----
  dominios: {
    list: (tipo?: string) => {
      const params = tipo ? `?tipo=${encodeURIComponent(tipo)}` : "";
      return request<Dominio[]>(`/dominios${params}`);
    },
  },

  // ---- Clientes ----
  clientes: {
    list: (params?: { page?: number; page_size?: number; q?: string }) => {
      const p = new URLSearchParams();
      if (params?.page) p.set("page", String(params.page));
      if (params?.page_size) p.set("page_size", String(params.page_size));
      if (params?.q) p.set("q", params.q);
      const qs = p.toString();
      return request<ClienteList>(`/clientes${qs ? `?${qs}` : ""}`);
    },
    get: (id: string) => request<Cliente>(`/clientes/${id}`),
    create: (body: ClienteInput) =>
      request<Cliente>("/clientes", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    busca: (cpf: string) =>
      request<Cliente[]>("/clientes/busca", {
        method: "POST",
        body: JSON.stringify({ cpf }),
      }),
    addVeiculo: (clienteId: string, body: VeiculoInput) =>
      request<Veiculo>(`/clientes/${clienteId}/veiculos`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    veiculos: (clienteId: string) =>
      request<Veiculo[]>(`/clientes/${clienteId}/veiculos`),
    addImovel: (clienteId: string, body: ImovelInput) =>
      request<Imovel>(`/clientes/${clienteId}/imoveis`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    imoveis: (clienteId: string) =>
      request<Imovel[]>(`/clientes/${clienteId}/imoveis`),
    update: (id: string, body: ClientePatch) =>
      request<Cliente>(`/clientes/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    archive: (id: string) =>
      request<void>(`/clientes/${id}`, { method: "DELETE" }),
    timeline: (id: string) =>
      request<TimelineItem[]>(`/clientes/${id}/timeline`),
  },

  // ---- Cotações ----
  cotacoes: {
    exportCsvUrl: () => `${BASE}/cotacoes/export/csv`,
    create: (body: CriarCotacaoInput) =>
      request<CotacaoCriada>("/cotacoes", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    get: (id: string) => request<Cotacao>(`/cotacoes/${id}`),
    list: (params?: { page?: number; page_size?: number }) => {
      const p = new URLSearchParams();
      if (params?.page) p.set("page", String(params.page));
      if (params?.page_size) p.set("page_size", String(params.page_size));
      const qs = p.toString();
      return request<PaginatedCotacoes>(`/cotacoes${qs ? `?${qs}` : ""}`);
    },
    recotar: (id: string) =>
      request<CotacaoCriada>(`/cotacoes/${id}/recotar`, { method: "POST" }),
    comparativo: (id: string) =>
      request<ItemComparativo[]>(`/cotacoes/${id}/comparativo`),
    comparativoPdfUrl: (id: string) =>
      `${BASE}/cotacoes/${id}/comparativo/pdf`,
    transmitir: (id: string, body: TransmitirInput) =>
      request<Proposta>(`/cotacoes/${id}/transmitir`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  // ---- Propostas ----
  propostas: {
    get: (id: string) => request<Proposta>(`/propostas/${id}`),
    parcelas: (id: string) => request<Parcela[]>(`/propostas/${id}/parcelas`),
    vincularApolice: (id: string, numero_apolice: string) =>
      request<Proposta>(`/propostas/${id}/apolice`, {
        method: "PATCH",
        body: JSON.stringify({ numero_apolice }),
      }),
  },

  // ---- Renovações ----
  renovacoes: {
    list: (dias?: number) => {
      const params = dias ? `?dias=${dias}` : "";
      return request<Renovacao[]>(`/renovacoes${params}`);
    },
  },

  // ---- Auditoria ----
  auditoria: {
    list: (params?: { page?: number; page_size?: number; tipo?: string; usuario_id?: string }) => {
      const p = new URLSearchParams();
      if (params?.page) p.set("page", String(params.page));
      if (params?.page_size) p.set("page_size", String(params.page_size));
      if (params?.tipo) p.set("tipo", params.tipo);
      if (params?.usuario_id) p.set("usuario_id", params.usuario_id);
      const qs = p.toString();
      return request<AuditoriaList>(`/auditoria${qs ? `?${qs}` : ""}`);
    },
    usuarios: () => request<AuditoriaUsuario[]>("/auditoria/usuarios"),
  },

  // ---- Usuários (admin) ----
  usuarios: {
    list: () => request<UsuarioAdmin[]>("/admin/usuarios"),
    criar: (data: { email: string; nome: string; papel: string; senha: string }) =>
      request<UsuarioAdmin>("/admin/usuarios", { method: "POST", body: JSON.stringify(data) }),
    atualizar: (id: string, data: { nome?: string; papel?: string; ativo?: boolean }) =>
      request<UsuarioAdmin>(`/admin/usuarios/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    resetSenha: (id: string, nova_senha: string) =>
      request<void>(`/admin/usuarios/${id}/reset-senha`, {
        method: "POST",
        body: JSON.stringify({ nova_senha }),
      }),
  },

  // ---- Home ----
  home: {
    corretor: () => request<HomeCorretorOut>("/home/corretor"),
    admin: () => request<HomeAdminOut>("/home/admin"),
  },

  // ---- Relatórios ----
  relatorios: {
    producao: (periodo: number, dateFrom?: string, dateTo?: string) => {
      const p = new URLSearchParams({ periodo: String(periodo) });
      if (dateFrom) p.set("date_from", dateFrom);
      if (dateTo) p.set("date_to", dateTo);
      return request<ProducaoOut[]>(`/relatorios/producao?${p}`);
    },
    funil: (periodo: number, dateFrom?: string, dateTo?: string) => {
      const p = new URLSearchParams({ periodo: String(periodo) });
      if (dateFrom) p.set("date_from", dateFrom);
      if (dateTo) p.set("date_to", dateTo);
      return request<FunilOut>(`/relatorios/funil?${p}`);
    },
    mix: (periodo: number, dateFrom?: string, dateTo?: string) => {
      const p = new URLSearchParams({ periodo: String(periodo) });
      if (dateFrom) p.set("date_from", dateFrom);
      if (dateTo) p.set("date_to", dateTo);
      return request<MixOut[]>(`/relatorios/mix?${p}`);
    },
    exportUrl: (tipo: string, periodo: number, fmt: "csv" | "xlsx") =>
      `${BASE}/relatorios/export/${fmt}?tipo=${tipo}&periodo=${periodo}`,
  },

  // ---- Dashboard ----
  dashboard: {
    get: (periodo = 30) =>
      request<DashboardOut>(`/dashboard?periodo=${periodo}`),
  },
};

// ---- Types ----

export interface Dominio {
  tipo: string;
  codigo: string;
  descricao: string;
  cia: string | null;
}

export interface ClienteList {
  items: Cliente[];
  total: number;
  page: number;
  page_size: number;
}

export interface Cliente {
  id: string;
  nome: string;
  email: string | null;
  telefone: string | null;
  data_nascimento: string | null;
  sexo: string | null;
  estado_civil: string | null;
  profissao: string | null;
  usuario_id: string;
  criado_em: string;
}

export interface ClienteInput {
  nome: string;
  cpf: string;
  email?: string;
  telefone?: string;
  data_nascimento?: string;
  sexo?: string;
  estado_civil?: string;
  profissao?: string;
}

export interface ClientePatch {
  nome?: string;
  email?: string;
  telefone?: string;
  data_nascimento?: string;
  sexo?: string;
  estado_civil?: string;
  profissao?: string;
}

export interface Veiculo {
  id: string;
  cliente_id: string;
  fipe_codigo: string | null;
  marca: string;
  modelo: string;
  ano_fabricacao: number;
  ano_modelo: number;
  placa: string | null;
  chassi: string | null;
  combustivel: string;
  finalidade: string;
  cep_pernoite: string;
}

export interface VeiculoInput {
  fipe_codigo?: string;
  marca: string;
  modelo: string;
  ano_fabricacao: number;
  ano_modelo: number;
  placa?: string;
  chassi?: string;
  combustivel: string;
  finalidade: string;
  cep_pernoite: string;
}

export interface Imovel {
  id: string;
  cliente_id: string;
  cep: string;
  logradouro: string | null;
  numero: string | null;
  tipo_imovel: string;
  tipo_construcao: string;
}

export interface ImovelInput {
  cep: string;
  logradouro?: string;
  numero?: string;
  tipo_imovel: string;
  tipo_construcao: string;
}

export interface CriarCotacaoInput {
  ramo: string;
  dados: Record<string, unknown>;
  cliente_id?: string;
  versao_anterior_id?: string;
}

export interface CotacaoCriada {
  id: string;
  status: string;
  ramo: string;
}

export interface Restricao {
  codigo: string;
  mensagem: string;
}

export interface Cotacao {
  id: string;
  status: string;
  ramo: string;
  cliente_id: string | null;
  cotacao_id_cia: string | null;
  premio_total: string | null;
  restricoes: Restricao[];
  mensagens: string[];
  necessita_vistoria: boolean;
  versao_anterior_id: string | null;
  criado_em: string;
  dados_risco: Record<string, unknown>;
  proposta_id: string | null;
}

export interface PaginatedCotacoes {
  items: Cotacao[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TransmitirInput {
  plano_pagamento: string;
  n_parcelas: number;
  comissao_pct: string;
  inicio_vigencia?: string;
  dados_negocio?: Record<string, unknown>;
  cia?: string;
}

export interface Proposta {
  id: string;
  cotacao_id: string;
  protocolo: string;
  plano_pagamento: string;
  n_parcelas: number;
  valor_parcela: string;
  comissao_parcela: string;
  comissao_pct: string;
  inicio_vigencia: string | null;
  transmitida_em: string;
  numero_apolice: string | null;
}

export interface Parcela {
  numero: number;
  vencimento: string | null;
  valor: string;
  comissao: string;
}

export interface ItemComparativo {
  cia: string;
  cotacao_id_cia: string | null;
  premio_total: string | null;
  annual_total: string | null;
  restricoes: Restricao[];
  mensagens: string[];
  necessita_vistoria: boolean;
  status: string;
}

export interface Renovacao {
  proposta_id: string;
  cotacao_id: string;
  cliente_id: string | null;
  protocolo: string;
  ramo: string;
  inicio_vigencia: string;
  fim_vigencia: string;
  dias_para_vencer: number;
  janela: "D30" | "D45" | "D60";
  premio_total: string | null;
}

export interface TimelineItem {
  tipo: string;
  data: string;
  dados: Record<string, unknown>;
}

// ---- Auditoria ----

export interface AuditoriaItem {
  id: number;
  tipo: string;
  usuario_id: string | null;
  usuario_nome: string | null;
  ip_origem: string | null;
  dados: Record<string, unknown>;
  criado_em: string;
}

export interface AuditoriaUsuario {
  id: string;
  nome: string;
}

export interface AuditoriaList {
  items: AuditoriaItem[];
  total: number;
  page: number;
  page_size: number;
}

// ---- Usuários (admin) ----

export interface UsuarioAdmin {
  id: string;
  email: string;
  nome: string;
  papel: string;
  ativo: boolean;
  criado_em: string;
}

// ---- Home ----

export interface ItemRenovacaoHome {
  proposta_id: string;
  cotacao_id: string;
  cliente_id: string | null;
  protocolo: string;
  ramo: string;
  inicio_vigencia: string;
  fim_vigencia: string;
  dias_para_vencer: number;
  janela: "D30" | "D45" | "D60";
  premio_total: string | null;
}

export interface ItemPropostaParada {
  cotacao_id: string;
  cliente_id: string | null;
  ramo: string;
  status: string;
  premio_total: string | null;
  criado_em: string;
}

export interface ItemCotacaoAbandonada {
  cotacao_id: string;
  cliente_id: string | null;
  ramo: string;
  status: string;
  criado_em: string;
}

export interface ItemParcelaVencendo {
  proposta_id: string;
  protocolo: string;
  numero_parcela: number;
  vencimento: string;
  valor: string;
  comissao: string;
}

export interface HomeCorretorOut {
  renovacoes: ItemRenovacaoHome[];
  propostas_paradas: ItemPropostaParada[];
  cotacoes_abandonadas: ItemCotacaoAbandonada[];
  parcelas_vencendo: ItemParcelaVencendo[];
}

export interface KpiRamo {
  ramo: string;
  count: number;
  premio_total: string;
}

export interface KpiCorretor {
  nome: string;
  cotacoes: number;
  propostas: number;
  premio_total: string;
}

export interface HomeAdminOut {
  segurados_vigentes: number;
  apolices_vigentes: number;
  cotacoes_em_andamento: number;
  premio_liquido: string;
  comissao_produzida: string;
  comissao_recebida: string;
  por_ramo: KpiRamo[];
  por_corretor: KpiCorretor[];
}

// ---- Relatórios ----

export interface ProducaoOut {
  corretor_id: string;
  corretor_nome: string;
  cotacoes: number;
  propostas: number;
  taxa_conversao: string;
  premio_total: string;
  comissao_prevista: string;
}

export interface FunilRamoOut {
  ramo: string;
  cotacoes: number;
  com_proposta: number;
  taxa_conversao: string;
  premio_medio: string;
}

export interface FunilOut {
  total_cotacoes: number;
  total_com_proposta: number;
  taxa_conversao_geral: string;
  por_ramo: FunilRamoOut[];
}

export interface MixOut {
  ramo: string;
  count: number;
  pct: string;
  premio_total: string;
}

// ---- Dashboard ----

export interface DashboardRamoOut {
  ramo: string;
  cotacoes: number;
  propostas: number;
  premio_total: string;
}

export interface DashboardCiaOut {
  cia: string;
  cotacoes: number;
  propostas: number;
  premio_total: string;
}

export interface DashboardOut {
  total_cotacoes: number;
  total_propostas: number;
  taxa_conversao: string;
  ticket_medio: string;
  por_ramo: DashboardRamoOut[];
  ranking_cias: DashboardCiaOut[];
}
