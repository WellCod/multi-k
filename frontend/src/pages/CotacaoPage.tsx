import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  api,
  type Cotacao,
  type Dominio,
  type Cliente,
  type ItemComparativo,
  type Proposta,
  ApiError,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Step1 } from "./cotacao/Step1";
import { Step2Auto } from "./cotacao/Step2Auto";
import { Step2Moto } from "./cotacao/Step2Moto";
import { Step2Imovel } from "./cotacao/Step2Imovel";
import { Step3 } from "./cotacao/Step3";
import { Step4 } from "./cotacao/Step4";
import { TransmitirModal } from "./cotacao/TransmitirModal";
import { ComparativoInline } from "./cotacao/ComparativoInline";
import { LoadingPanel } from "./cotacao/shared";
import { type Step1Data, type Step2Data, type Step3Data, type Step4Data } from "./cotacao/types";

const STORAGE_KEY = "mk_cotacao_rascunho";
const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 120_000;

interface Rascunho {
  ramo: string;
  step: number;
  step2?: Step2Data;
  step3?: Step3Data;
  step4?: Step4Data;
  clienteId?: string;
}

function saveRascunho(r: Rascunho) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(r));
}

function loadRascunho(): Rascunho | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Rascunho) : null;
  } catch {
    return null;
  }
}

function clearRascunho() {
  sessionStorage.removeItem(STORAGE_KEY);
}

const STEP_LABELS = [
  "Proponente",
  "Dados do risco",
  "Coberturas",
  "Vigência",
  "Resultado",
];

export function CotacaoPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [dominios, setDominios] = useState<Dominio[]>([]);
  const [ramo, setRamo] = useState<string>(() => {
    return loadRascunho()?.ramo ?? "auto";
  });
  const [step, setStep] = useState<number>(() => {
    return loadRascunho()?.step ?? 1;
  });
  const [step1Data, setStep1Data] = useState<Step1Data | undefined>(undefined);
  const [step2Data, setStep2Data] = useState<Step2Data | undefined>(
    () => loadRascunho()?.step2,
  );
  const [step3Data, setStep3Data] = useState<Step3Data | undefined>(
    () => loadRascunho()?.step3,
  );
  const [step4Data, setStep4Data] = useState<Step4Data | undefined>(
    () => loadRascunho()?.step4,
  );
  const [clienteId, setClienteId] = useState<string | undefined>(
    () => loadRascunho()?.clienteId,
  );

  const [cotacaoId, setCotacaoId] = useState<string | null>(null);
  const [cotacao, setCotacao] = useState<Cotacao | null>(null);
  const [polling, setPolling] = useState(false);
  const [pollingSeconds, setPollingSeconds] = useState(0);
  const [pollCancelled, setPollCancelled] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollingSecRef = useRef(0);
  const sseRef = useRef<EventSource | null>(null);

  const [criando, setCriando] = useState(false);
  const [cotacaoErrMsg, setCotacaoErrMsg] = useState<string | null>(null);

  const [itensComparativo, setItensComparativo] = useState<ItemComparativo[]>([]);
  const [proposta, setProposta] = useState<Proposta | null>(null);
  const [showTransmitir, setShowTransmitir] = useState(false);
  const [transmitirCia, setTransmitirCia] = useState("fake");

  const [recotarError, setRecotarError] = useState<string | null>(null);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const recotar = searchParams.get("recotar");
  const clienteParam = searchParams.get("cliente");

  useEffect(() => {
    api.dominios.list().then(setDominios).catch(() => {});
  }, []);

  useEffect(() => {
    if (!clienteParam) return;
    clearRascunho();
    setStep(1);
    setStep2Data(undefined);
    setStep3Data(undefined);
    setStep4Data(undefined);
    setClienteId(clienteParam);
  }, [clienteParam]);

  useEffect(() => {
    if (!recotar) return;
    let cancelled = false;
    api.cotacoes.get(recotar).then((c) => {
      if (cancelled) return;
      setRamo(c.ramo);
      setStep2Data(c.dados_risco as Record<string, unknown>);
      if (c.cliente_id) setClienteId(c.cliente_id);
    }).catch(() => {
      if (!cancelled) setRecotarError("Não foi possível carregar os dados da cotação anterior.");
    });
    return () => { cancelled = true; };
  }, [recotar]);

  useEffect(() => {
    if (!cotacaoId || !cotacao || polling) return;
    if (cotacao.status !== "sucesso" && cotacao.status !== "restricao") return;
    let cancelled = false;
    api.cotacoes
      .comparativo(cotacaoId)
      .then((items) => { if (!cancelled) setItensComparativo(items); })
      .catch(() => { if (!cancelled) setItensComparativo([]); });
    return () => { cancelled = true; };
  }, [cotacaoId, cotacao, polling]);

  const persistRascunho = useCallback(
    (patch: Partial<Rascunho>) => {
      const current = loadRascunho() ?? { ramo, step };
      saveRascunho({ ...current, ...patch });
    },
    [ramo, step],
  );

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
    if (sseRef.current) {
      sseRef.current.close();
      sseRef.current = null;
    }
    setPolling(false);
  }, []);

  useEffect(() => () => {
    if (pollRef.current) clearTimeout(pollRef.current);
    if (sseRef.current) sseRef.current.close();
  }, []);

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      const start = Date.now();
      pollingSecRef.current = 0;
      setPollingSeconds(0);
      setPolling(true);
      setPollCancelled(false);

      if (typeof EventSource !== "undefined") {
        const apiBase = import.meta.env.VITE_API_URL ?? "/api";
        const es = new EventSource(`${apiBase}/events`, { withCredentials: true });
        sseRef.current = es;
        es.onmessage = async (ev) => {
          try {
            const data = JSON.parse(ev.data as string) as { tipo?: string; cotacao_id?: string };
            if (data.tipo === "cotacao.pronta" && data.cotacao_id === id) {
              const c = await api.cotacoes.get(id);
              setCotacao(c);
              if (c.status !== "aguardando" && c.status !== "processando") {
                stopPolling();
                clearRascunho();
              }
            }
          } catch { /* ignora erros de parse ou rede */ }
        };
        es.onerror = () => { sseRef.current?.close(); sseRef.current = null; };
      }

      const tick = async () => {
        if (Date.now() - start > POLL_TIMEOUT_MS) {
          stopPolling();
          return;
        }
        pollingSecRef.current += POLL_INTERVAL_MS / 1000;
        setPollingSeconds(Math.floor(pollingSecRef.current));

        try {
          const c = await api.cotacoes.get(id);
          setCotacao(c);
          if (c.status !== "aguardando" && c.status !== "processando") {
            stopPolling();
            clearRascunho();
            return;
          }
        } catch {
          // erro de rede — mantém polling
        }

        pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
      };

      pollRef.current = setTimeout(tick, POLL_INTERVAL_MS);
    },
    [stopPolling],
  );

  const handleRamoChange = (r: string) => {
    setRamo(r);
    persistRascunho({ ramo: r });
  };

  const handleStep1 = (data: Step1Data, cliente: Cliente | null) => {
    setStep1Data(data);
    setClienteId(cliente?.id);
    setStep(2);
    persistRascunho({ step: 2, clienteId: cliente?.id });
  };

  const handleStep2 = (data: Step2Data) => {
    setStep2Data(data);
    setStep(3);
    persistRascunho({ step2: data, step: 3 });
  };

  const handleStep3 = (data: Step3Data) => {
    setStep3Data(data);
    setStep(4);
    persistRascunho({ step3: data, step: 4 });
  };

  const handleStep4 = async (data: Step4Data) => {
    setStep4Data(data);
    setCotacaoErrMsg(null);
    persistRascunho({ step4: data });

    const step2Limpo = { ...(step2Data ?? {}) };
    if (!step2Limpo.condutor_diferente) {
      delete step2Limpo.condutor_diferente;
      delete step2Limpo.condutor_cpf;
      delete step2Limpo.condutor_nome;
      delete step2Limpo.condutor_sexo;
      delete step2Limpo.condutor_nascimento;
      delete step2Limpo.condutor_parentesco;
    } else {
      delete step2Limpo.condutor_diferente;
    }

    const dados: Record<string, unknown> = {
      ...step2Limpo,
      coberturas: step3Data?.coberturas ?? [],
      plano_pagamento: data.plano_pagamento,
      inicio_vigencia: data.inicio_vigencia,
      fim_vigencia: data.fim_vigencia,
      ...(step1Data
        ? {
            proponente: {
              cpf: step1Data.cpf,
              telefone: step1Data.telefone,
              nome: step1Data.nome,
              email: step1Data.email,
              estado_civil: step1Data.estado_civil,
              profissao: step1Data.profissao,
              data_nascimento: step1Data.data_nascimento,
              sexo: step1Data.sexo,
            },
          }
        : {}),
    };

    setCriando(true);
    try {
      const created = await api.cotacoes.create({
        ramo,
        dados,
        cliente_id: clienteId,
        versao_anterior_id: recotar ?? undefined,
      });
      setCotacaoId(created.id);
      setStep(5);
      persistRascunho({ step: 5 });
      startPolling(created.id);
    } catch (err) {
      setCotacaoErrMsg(
        err instanceof ApiError ? err.message : "Erro ao solicitar cotação. Tente novamente."
      );
    } finally {
      setCriando(false);
    }
  };

  const handleRecotar = () => {
    if (!cotacaoId) return;
    navigate(`/cotacao?recotar=${cotacaoId}`);
  };

  const handleCancel = () => {
    setPollCancelled(true);
    stopPolling();
    clearRascunho();
  };

  const handleNewCotacao = () => {
    if (step > 1) { setShowCancelConfirm(true); return; }
    clearRascunho();
    setStep(1);
    setStep1Data(undefined);
    setStep2Data(undefined);
    setStep3Data(undefined);
    setStep4Data(undefined);
    setCotacaoId(null);
    setCotacao(null);
    setItensComparativo([]);
    setProposta(null);
    setShowTransmitir(false);
    navigate("/cotacao");
  };

  const confirmDiscard = () => {
    setShowCancelConfirm(false);
    clearRascunho();
    setStep(1);
    setStep1Data(undefined);
    setStep2Data(undefined);
    setStep3Data(undefined);
    setStep4Data(undefined);
    setCotacaoId(null);
    setCotacao(null);
    setItensComparativo([]);
    setProposta(null);
    setShowTransmitir(false);
    navigate("/cotacao");
  };

  return (
    <div className="max-w-2xl mx-auto">
      {showCancelConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => { if (e.target === e.currentTarget) setShowCancelConfirm(false); }}
        >
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-xl w-full max-w-sm mx-4 p-6 space-y-4">
            <h2 className="text-base font-semibold text-gray-900 dark:text-white">Descartar cotação?</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              O rascunho atual será perdido. Deseja continuar?
            </p>
            <div className="flex gap-2 justify-end">
              <Button type="button" variant="outline" size="sm" onClick={() => setShowCancelConfirm(false)}>
                Continuar editando
              </Button>
              <Button type="button" size="sm" onClick={confirmDiscard}
                className="bg-red-600 hover:bg-red-700 text-white border-red-600">
                Descartar
              </Button>
            </div>
          </div>
        </div>
      )}

      {recotarError && (
        <div className="mb-4 text-sm text-yellow-800 dark:text-yellow-300 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded px-4 py-3">
          {recotarError}
        </div>
      )}

      {step === 1 && (
        <div className="mb-6 flex gap-3">
          {(["auto", "moto", "imovel"] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => handleRamoChange(r)}
              className={`px-4 py-2 rounded text-sm font-medium border transition-colors ${
                ramo === r
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 border-gray-300 dark:border-gray-600 hover:border-blue-400"
              }`}
            >
              {r === "auto" ? "Auto" : r === "moto" ? "Moto" : "Imóvel"}
            </button>
          ))}
        </div>
      )}

      <div className="mb-6">
        <div className="flex items-center gap-1 mb-2">
          {STEP_LABELS.map((_label, i) => {
            const s = i + 1;
            return (
              <div key={s} className="flex items-center gap-1 flex-1">
                <div
                  className={`h-1.5 flex-1 rounded-full transition-colors ${
                    s <= step ? "bg-blue-500" : "bg-gray-200 dark:bg-gray-600"
                  }`}
                />
              </div>
            );
          })}
        </div>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Passo {step} de 5 — {STEP_LABELS[step - 1]}
        </p>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-6">
        {step === 1 && (
          <Step1
            dominios={dominios}
            defaultValues={step1Data}
            onNext={handleStep1}
          />
        )}

        {step === 2 && ramo === "auto" && (
          <Step2Auto
            defaultValues={step2Data}
            onBack={() => setStep(1)}
            onNext={handleStep2}
          />
        )}

        {step === 2 && ramo === "moto" && (
          <Step2Moto
            defaultValues={step2Data}
            onBack={() => setStep(1)}
            onNext={handleStep2}
          />
        )}

        {step === 2 && ramo === "imovel" && (
          <Step2Imovel
            dominios={dominios}
            defaultValues={step2Data}
            onBack={() => setStep(1)}
            onNext={handleStep2}
          />
        )}

        {step === 3 && (
          <Step3
            ramo={ramo}
            dominios={dominios}
            defaultValues={step3Data}
            onBack={() => setStep(2)}
            onNext={handleStep3}
          />
        )}

        {step === 4 && (
          <Step4
            dominios={dominios}
            defaultValues={step4Data}
            onBack={() => setStep(3)}
            onNext={handleStep4}
            submitting={criando}
            serverError={cotacaoErrMsg}
          />
        )}

        {step === 5 && (
          <div className="space-y-4">
            {polling && !pollCancelled && (
              <LoadingPanel seconds={pollingSeconds} onCancel={handleCancel} />
            )}

            {pollCancelled && (
              <div className="text-sm text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-700/50 rounded p-4">
                Consulta cancelada.{" "}
                <button
                  type="button"
                  className="text-blue-600 dark:text-blue-400 underline"
                  onClick={() => {
                    if (cotacaoId) startPolling(cotacaoId);
                  }}
                >
                  Retomar
                </button>
              </div>
            )}

            {cotacao && (
              <ComparativoInline
                cotacao={cotacao}
                cotacaoId={cotacaoId!}
                itens={itensComparativo}
                proposta={proposta}
                onEmitir={(cia) => { setTransmitirCia(cia); setShowTransmitir(true); }}
                onRecotar={handleRecotar}
              />
            )}

            <div className="pt-2 flex justify-between">
              <Button variant="outline" onClick={() => setStep(4)}>
                ← Voltar
              </Button>
              <Button variant="ghost" onClick={handleNewCotacao}>
                Nova cotação
              </Button>
            </div>
          </div>
        )}
      </div>

      {showTransmitir && cotacaoId && (
        <TransmitirModal
          cotacaoId={cotacaoId}
          ramo={cotacao?.ramo}
          cia={transmitirCia}
          vigenciaInicio={step4Data?.inicio_vigencia}
          onClose={() => setShowTransmitir(false)}
          onSuccess={(p) => {
            setProposta(p);
            setShowTransmitir(false);
          }}
        />
      )}
    </div>
  );
}
