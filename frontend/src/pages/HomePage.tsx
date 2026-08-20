import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import {
  api,
  type HomeAdminOut,
  type HomeCorretorOut,
  type ItemCotacaoAbandonada,
  type ItemParcelaVencendo,
  type ItemPropostaParada,
  type ItemRenovacaoHome,
  type KpiCorretor,
  type KpiRamo,
} from "@/lib/api";

function fmtReal(v: string | null | undefined) {
  if (!v) return "—";
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtDate(d: string) {
  return new Date(d + "T12:00:00").toLocaleDateString("pt-BR");
}

function fmtDatetime(d: string) {
  return new Date(d).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Corretor — seções da fila de trabalho
// ---------------------------------------------------------------------------

function SecaoRenovacoes({ items }: { items: ItemRenovacaoHome[] }) {
  const navigate = useNavigate();
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
        Renovações próximas ({items.length})
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400">
              <th className="px-3 py-2">Protocolo</th>
              <th className="px-3 py-2">Ramo</th>
              <th className="px-3 py-2">Prêmio</th>
              <th className="px-3 py-2">Vigência até</th>
              <th className="px-3 py-2">Dias</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr
                key={r.proposta_id}
                className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
              >
                <td className="px-3 py-2 font-mono text-xs text-gray-700 dark:text-gray-300">
                  {r.protocolo}
                </td>
                <td className="px-3 py-2 capitalize text-gray-900 dark:text-white">{r.ramo}</td>
                <td className="px-3 py-2 text-gray-900 dark:text-white">{fmtReal(r.premio_total)}</td>
                <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{fmtDate(r.fim_vigencia)}</td>
                <td className="px-3 py-2 font-semibold text-center">
                  <span
                    className={
                      r.dias_para_vencer <= 30
                        ? "text-red-700 dark:text-red-400"
                        : r.dias_para_vencer <= 45
                          ? "text-orange-600 dark:text-orange-400"
                          : "text-yellow-600 dark:text-yellow-400"
                    }
                  >
                    {r.dias_para_vencer}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <button
                    className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
                    onClick={() => navigate(`/cotacao?recotar=${r.cotacao_id}`)}
                  >
                    Renovar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SecaoPropostasParadas({ items }: { items: ItemPropostaParada[] }) {
  const navigate = useNavigate();
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
        Cotações sem proposta há 2+ dias ({items.length})
      </h2>
      <div className="space-y-2">
        {items.map((p) => (
          <div
            key={p.cotacao_id}
            className="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-4 py-2.5 text-sm"
          >
            <div>
              <span className="capitalize font-medium text-gray-900 dark:text-white">{p.ramo}</span>
              <span className="text-gray-400 dark:text-gray-500 text-xs ml-2">{fmtDatetime(p.criado_em)}</span>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-gray-700 dark:text-gray-300">{fmtReal(p.premio_total)}</span>
              <button
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                onClick={() => navigate(`/cotacoes/${p.cotacao_id}/comparativo`)}
              >
                Ver
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function SecaoCotacoesAbandonadas({ items }: { items: ItemCotacaoAbandonada[] }) {
  const navigate = useNavigate();
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
        Cotações em processamento há 2+ dias ({items.length})
      </h2>
      <div className="space-y-2">
        {items.map((c) => (
          <div
            key={c.cotacao_id}
            className="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-4 py-2.5 text-sm"
          >
            <div>
              <span className="capitalize font-medium text-gray-900 dark:text-white">{c.ramo}</span>
              <span className="text-gray-400 dark:text-gray-500 text-xs ml-2">{fmtDatetime(c.criado_em)}</span>
            </div>
            <button
              className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
              onClick={() => navigate(`/cotacao?recotar=${c.cotacao_id}`)}
            >
              Recotar
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

function SecaoParcelasVencendo({ items }: { items: ItemParcelaVencendo[] }) {
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-2">
        Parcelas vencendo em 30 dias ({items.length})
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500 dark:text-gray-400">
              <th className="px-3 py-2">Protocolo</th>
              <th className="px-3 py-2">Parcela</th>
              <th className="px-3 py-2">Vencimento</th>
              <th className="px-3 py-2">Valor</th>
              <th className="px-3 py-2">Comissão</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr
                key={`${p.proposta_id}-${p.numero_parcela}`}
                className="border-b border-gray-100 dark:border-gray-700"
              >
                <td className="px-3 py-2 font-mono text-xs text-gray-700 dark:text-gray-300">
                  {p.protocolo}
                </td>
                <td className="px-3 py-2 text-gray-900 dark:text-white">{p.numero_parcela}ª</td>
                <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{fmtDate(p.vencimento)}</td>
                <td className="px-3 py-2 text-gray-900 dark:text-white">{fmtReal(p.valor)}</td>
                <td className="px-3 py-2 text-green-700 dark:text-green-400">{fmtReal(p.comissao)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function HomeCorretor() {
  const [data, setData] = useState<HomeCorretorOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.home
      .corretor()
      .then(setData)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-gray-500 dark:text-gray-400">Carregando…</p>;
  if (err) return <p className="text-sm text-red-600">{err}</p>;
  if (!data) return null;

  const total =
    data.renovacoes.length +
    data.propostas_paradas.length +
    data.cotacoes_abandonadas.length +
    data.parcelas_vencendo.length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Minha fila</h1>
        <button
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
          onClick={() => navigate("/cotacao")}
        >
          Nova cotação
        </button>
      </div>

      {total === 0 ? (
        <div className="text-center py-16 text-gray-500 dark:text-gray-400">
          <p className="text-base">Nenhuma pendência no momento.</p>
          <p className="text-sm mt-1">Use o menu para iniciar uma nova cotação.</p>
        </div>
      ) : (
        <div className="space-y-8">
          <SecaoRenovacoes items={data.renovacoes} />
          <SecaoPropostasParadas items={data.propostas_paradas} />
          <SecaoCotacoesAbandonadas items={data.cotacoes_abandonadas} />
          <SecaoParcelasVencendo items={data.parcelas_vencendo} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Admin — KPIs
// ---------------------------------------------------------------------------

function KpiCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
      <p className="text-lg font-semibold text-gray-900 dark:text-white mt-0.5">{value}</p>
    </div>
  );
}

function BarraHorizontal({ items }: { items: { label: string; value: number; max: number }[] }) {
  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          <span className="w-24 text-xs text-gray-600 dark:text-gray-400 text-right capitalize shrink-0">
            {item.label}
          </span>
          <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-700 rounded overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded"
              style={{ width: item.max > 0 ? `${(item.value / item.max) * 100}%` : "0%" }}
            />
          </div>
          <span className="text-xs text-gray-700 dark:text-gray-300 w-8 text-right shrink-0">
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}

function HomeAdmin() {
  const [data, setData] = useState<HomeAdminOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.home
      .admin()
      .then(setData)
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Erro"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-gray-500 dark:text-gray-400">Carregando…</p>;
  if (err) return <p className="text-sm text-red-600">{err}</p>;
  if (!data) return null;

  const maxRamo = Math.max(...(data.por_ramo as KpiRamo[]).map((r) => r.count), 1);
  const maxCorretor = Math.max(...(data.por_corretor as KpiCorretor[]).map((c) => c.propostas), 1);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-gray-900 dark:text-white">Visão geral</h1>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard label="Segurados vigentes" value={data.segurados_vigentes} />
        <KpiCard label="Apólices vigentes" value={data.apolices_vigentes} />
        <KpiCard label="Cotações em andamento" value={data.cotacoes_em_andamento} />
        <KpiCard label="Prêmio líquido" value={fmtReal(data.premio_liquido)} />
        <KpiCard label="Comissão produzida" value={fmtReal(data.comissao_produzida)} />
        <KpiCard label="Comissão recebida" value={fmtReal(data.comissao_recebida)} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {data.por_ramo.length > 0 && (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
              Mix por ramo
            </h2>
            <BarraHorizontal
              items={(data.por_ramo as KpiRamo[])
                .sort((a, b) => b.count - a.count)
                .map((r) => ({ label: r.ramo, value: r.count, max: maxRamo }))}
            />
          </div>
        )}

        {data.por_corretor.length > 0 && (
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
            <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
              Propostas por corretor
            </h2>
            <BarraHorizontal
              items={(data.por_corretor as KpiCorretor[])
                .sort((a, b) => b.propostas - a.propostas)
                .map((c) => ({ label: c.nome, value: c.propostas, max: maxCorretor }))}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Página — despacha por papel
// ---------------------------------------------------------------------------

export function HomePage() {
  const { user } = useAuth();
  if (!user) return null;
  return user.papel === "admin" ? <HomeAdmin /> : <HomeCorretor />;
}
