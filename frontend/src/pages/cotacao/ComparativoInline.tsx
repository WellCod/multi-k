import { useNavigate } from "react-router-dom";
import { api, type Cotacao, type ItemComparativo, type Proposta } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/Tooltip";
import { formatBRL } from "@/lib/utils";
import { StatusBadge } from "./shared";

interface ComparativoInlineProps {
  cotacao: Cotacao;
  cotacaoId: string;
  itens: ItemComparativo[];
  proposta: Proposta | null;
  onEmitir: (cia: string) => void;
  onRecotar: () => void;
}

export function ComparativoInline({
  cotacao,
  cotacaoId,
  itens,
  proposta,
  onEmitir,
  onRecotar,
}: ComparativoInlineProps) {
  const navigate = useNavigate();

  if (proposta) {
    return (
      <div className="bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 rounded-lg p-5 space-y-1">
        <p className="font-semibold text-green-800 dark:text-green-300">Proposta transmitida com sucesso!</p>
        <p className="text-sm text-green-700 dark:text-green-400">
          Protocolo:{" "}
          <span className="font-mono font-semibold">{proposta.protocolo}</span>
        </p>
        <p className="text-sm text-green-700 dark:text-green-400">
          {proposta.n_parcelas}× de {formatBRL(proposta.valor_parcela)}
        </p>
        {cotacao.cliente_id && (
          <Button
            className="mt-3"
            size="sm"
            variant="outline"
            onClick={() => navigate(`/clientes/${cotacao.cliente_id}`)}
          >
            Ver timeline do cliente
          </Button>
        )}
      </div>
    );
  }

  if (cotacao.status === "erro") {
    return (
      <div className="rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/30 p-6">
        <h3 className="font-medium text-red-800 dark:text-red-300 mb-2">Cotação não realizada</h3>
        <p className="text-sm text-red-700 dark:text-red-400">
          {cotacao.mensagens[0] ??
            "A seguradora não pôde calcular o prêmio para este risco."}
        </p>
        <Tooltip text="Reenvia os mesmos dados para a seguradora tentar calcular novamente">
          <Button variant="outline" size="sm" className="mt-4" onClick={onRecotar}>
            Tentar novamente
          </Button>
        </Tooltip>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-gray-900 dark:text-white">
          Resultados —{" "}
          {cotacao.ramo.charAt(0).toUpperCase() + cotacao.ramo.slice(1)}
        </h3>
        <StatusBadge status={cotacao.status} />
      </div>

      {cotacao.necessita_vistoria && (
        <p className="text-sm font-medium text-yellow-700 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-800 rounded px-3 py-2">
          Vistoria prévia obrigatória — prazo de emissão estendido.
        </p>
      )}

      {itens.length === 0 ? (
        <p className="text-sm text-gray-500 py-4">Processando resultados…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 dark:bg-gray-700/50 border-b border-gray-200 dark:border-gray-700 text-left">
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Seguradora</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Mensal</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Anual</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Observações</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Vistoria</th>
                <th className="px-4 py-2 font-medium text-gray-700 dark:text-gray-300">Status</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {(() => {
                const aprovados = itens.filter(
                  (it) => (it.status === "sucesso" || it.status === "restricao") && it.premio_total,
                );
                const minPreco =
                  aprovados.length > 0
                    ? Math.min(...aprovados.map((it) => parseFloat(it.premio_total!)))
                    : null;
                return itens.map((item, i) => {
                  const isBest =
                    minPreco !== null &&
                    item.premio_total !== null &&
                    parseFloat(item.premio_total) === minPreco;
                  return (
                    <tr
                      key={i}
                      className={
                        isBest
                          ? "border-b border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20"
                          : "border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                      }
                    >
                      <td className="px-4 py-3 font-semibold uppercase">
                        {item.cia}
                        {isBest && (
                          <span className="ml-2 inline-block text-[10px] font-bold uppercase tracking-wide text-green-700 dark:text-green-400 bg-green-100 dark:bg-green-900/50 border border-green-300 dark:border-green-700 rounded px-1.5 py-0.5">
                            Melhor preço
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono">{formatBRL(item.premio_total)}</td>
                      <td className="px-4 py-3 font-mono text-gray-500 dark:text-gray-400">
                        {item.annual_total ? formatBRL(item.annual_total) : <span className="text-gray-300 dark:text-gray-600">—</span>}
                      </td>
                      <td className="px-4 py-3 max-w-xs">
                        {item.restricoes.length === 0 && item.mensagens.length === 0 ? (
                          <span className="text-gray-400">—</span>
                        ) : (
                          <>
                            {item.restricoes.map((r) => (
                              <span key={r.codigo} className="block text-xs text-yellow-700 dark:text-yellow-400">
                                {r.codigo}: {r.mensagem}
                              </span>
                            ))}
                            {item.mensagens.map((m, j) => (
                              <span key={j} className="block text-xs text-blue-600 dark:text-blue-400">
                                {m}
                              </span>
                            ))}
                          </>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {item.necessita_vistoria ? (
                          <span className="text-yellow-700 dark:text-yellow-400 text-xs font-medium">Sim</span>
                        ) : (
                          <span className="text-gray-400 text-xs">Não</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="px-4 py-3">
                        {(item.status === "sucesso" || item.status === "restricao") && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => onEmitir(item.cia)}
                          >
                            Emitir
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                });
              })()}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center gap-3 flex-wrap">
        <a
          href={api.cotacoes.comparativoPdfUrl(cotacaoId)}
          target="_blank"
          rel="noreferrer"
          className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          Baixar PDF
        </a>
        <Tooltip text="Refaz a cotação com os mesmos dados do risco, gerando um novo comparativo">
          <Button variant="outline" onClick={onRecotar}>
            Refazer cotação
          </Button>
        </Tooltip>
      </div>
    </div>
  );
}
