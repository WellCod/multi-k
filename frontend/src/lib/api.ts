const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (res.status === 401) {
    // Let auth context handle redirect
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

export const api = {
  auth: {
    login: (email: string, senha: string) =>
      request<LoginOut>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, senha }),
      }),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
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
    list: () => request<Cliente[]>("/clientes"),
    get: (id: string) => request<Cliente>(`/clientes/${id}`),
    create: (body: ClienteInput) =>
      request<Cliente>("/clientes", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    busca: (cpf: string) =>
      request<Cliente[]>(`/clientes/busca?cpf=${encodeURIComponent(cpf)}`),
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
    timeline: (id: string) =>
      request<TimelineItem[]>(`/clientes/${id}/timeline`),
  },

  // ---- Cotações ----
  cotacoes: {
    create: (body: CriarCotacaoInput) =>
      request<CotacaoCriada>("/cotacoes", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    get: (id: string) => request<Cotacao>(`/cotacoes/${id}`),
    list: () => request<Cotacao[]>("/cotacoes"),
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
  },

  // ---- Renovações ----
  renovacoes: {
    list: (dias?: number) => {
      const params = dias ? `?dias=${dias}` : "";
      return request<Renovacao[]>(`/renovacoes${params}`);
    },
  },

};

// ---- Types ----

export interface Dominio {
  tipo: string;
  codigo: string;
  descricao: string;
  cia: string | null;
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
}

export interface TransmitirInput {
  plano_pagamento: string;
  n_parcelas: number;
  comissao_pct: string;
  inicio_vigencia?: string;
  dados_negocio?: Record<string, unknown>;
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
