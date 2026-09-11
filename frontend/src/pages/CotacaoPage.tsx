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
import { Dialog } from "@/components/Dialog";
import { Step1 } from "./cotacao/Step1";
import { Step2Auto } from "./cotacao/Step2Auto";
import { Step2Moto } from "./cotacao/Step2Moto";
import { Step2Imovel } from "./cotacao/Step2Imovel";
import { Step4 } from "./cotacao/Step4";
import { TransmitirModal } from "./cotacao/TransmitirModal";
import { ComparativoInline } from "./cotacao/ComparativoInline";
import { useInsurers } from "@/hooks/useInsurers";
import { type Step1Data, type Step2Data, type Step3Data, type Step4Data } from "./cotacao/types";

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 120_000;

interface Rascunho {
  flowVersion?: number;
  ramo: string;
  step: number;
  step1?: Step1Data;
  step2?: Step2Data;
  step3?: Step3Data;
  step4?: Step4Data;
  clienteId?: string;
}

const STEP_LABELS = [
  "Identificação",
  "Objeto",
  "Perfil",
  "Coberturas",
  "Resultado",
];

export function CotacaoPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const draftRef = useRef<Rascunho | null>(null);
  const versionRef = useRef(0);
  const saveQueue = useRef<Promise<void>>(Promise.resolve());
  const [draftReady, setDraftReady] = useState(false);
  const [saveStatus, setSaveStatus] = useState("Carregando rascunho…");
  function loadRascunho() { return draftRef.current; }
  function saveRascunho(value: Rascunho) {
    value = { ...value, flowVersion: 2 };
    draftRef.current = value;
    setSaveStatus("Salvando…");
    saveQueue.current = saveQueue.current.then(async () => {
      try {
        const response = await api.rascunho.save(value, versionRef.current);
        versionRef.current = response.versao;
        setSaveStatus("Passo salvo no servidor");
      } catch {
        setSaveStatus("Não foi possível salvar. Mantenha esta tela aberta e tente avançar novamente.");
      }
    });
  }
  function clearRascunho() {
    draftRef.current = null;
    saveQueue.current = saveQueue.current.then(async () => {
      try { await api.rascunho.clear(); versionRef.current = 0; setSaveStatus("Novo rascunho"); }
      catch { setSaveStatus("Não foi possível limpar o rascunho no servidor."); }
    });
  }

  const [dominios, setDominios] = useState<Dominio[]>([]);
  const { items: insurers, error: insurersError } = useInsurers();
  const [selectedInsurers, setSelectedInsurers] = useState<string[]>([]);
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
  const [transmitirCia, setTransmitirCia] = useState("");

  const [recotarError, setRecotarError] = useState<string | null>(null);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const recotar = searchParams.get("recotar");
  const clienteParam = searchParams.get("cliente");

  useEffect(() => { setSelectedInsurers(insurers.filter(item => item.ramos.includes(ramo)).map(item => item.id)); }, [insurers, ramo]);

  useEffect(() => {
    let disposed = false;
    api.rascunho.get().then(response => {
      if (disposed) return;
      versionRef.current = response.versao;
      if (response.dados && !recotar && !clienteParam) {
        const draft = response.dados as unknown as Rascunho;
        draftRef.current = draft;
        setRamo(draft.ramo);
        setStep(draft.flowVersion === 2 ? Math.max(1, Math.min(draft.step, 4)) : 1);
        setStep1Data(draft.step1);
        setStep2Data(draft.step2);
        setStep3Data(draft.step3);
        setStep4Data(draft.step4);
        setClienteId(draft.clienteId);
        setSaveStatus("Rascunho recuperado do servidor");
      } else setSaveStatus("Novo rascunho");
    }).catch(() => { if (!disposed) setSaveStatus("Autosave indisponível. O rascunho não está protegido contra perda de sessão."); })
      .finally(() => { if (!disposed) setDraftReady(true); });
    return () => { disposed = true; };
  }, [recotar, clienteParam]);

  useEffect(() => {
    if (!draftReady) return;
    const frame = requestAnimationFrame(() => document.querySelector<HTMLElement>("#quotation-step input, #quotation-step select, #quotation-step button")?.focus());
    return () => cancelAnimationFrame(frame);
  }, [step, draftReady]);


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
    if (!cotacaoId || !cotacao) return;
    let cancelled = false;
    api.cotacoes
      .comparativo(cotacaoId)
      .then((items) => { if (!cancelled) setItensComparativo(items); })
      .catch(() => { /* Preserve partial results during temporary network failures. */ });
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
          setPollCancelled(true);
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
    if (r === ramo) return;
    setRamo(r);
    setStep2Data(undefined);
    setStep3Data(undefined);
    setStep4Data(undefined);
    persistRascunho({ ramo: r, step2: undefined, step3: undefined, step4: undefined });
  };

  const handleStep1 = (data: Step1Data, cliente: Cliente | null) => {
    setStep1Data(data);
    setClienteId(cliente?.id);
    setStep(2);
    persistRascunho({ step1: data, step: 2, clienteId: cliente?.id });
  };

  const handleStep2 = (data: Step2Data) => {
    const merged = { ...step2Data, ...data };
    setStep2Data(merged);
    setStep(3);
    persistRascunho({ step2: merged, step: 3 });
  };

  const handleStep3 = (data: Step2Data) => {
    const merged = { ...step2Data, ...data };
    setStep2Data(merged);
    setStep(4);
    persistRascunho({ step2: merged, step: 4 });
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
      coberturas: data.coberturas,
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
        cias: selectedInsurers,
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

  const handleCancel = async (cia?: string) => {
    if (!cotacaoId) return;
    try {
      await api.cotacoes.cancelar(cotacaoId, cia);
      setItensComparativo(await api.cotacoes.comparativo(cotacaoId));
      setCotacao(await api.cotacoes.get(cotacaoId));
      if (!cia) stopPolling();
    } catch { setCotacaoErrMsg("Não foi possível cancelar. A consulta continua; tente novamente."); }
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

  if (!draftReady) return <p role="status">Carregando rascunho…</p>;
  return (
    <div onKeyDown={event => { if (event.altKey && event.key === "ArrowLeft" && step > 1 && !criando && !showCancelConfirm && !showTransmitir) { event.preventDefault(); setStep(value => value - 1); } }} className={step === 5 ? "w-full" : "max-w-3xl mx-auto w-full"}>
      {showCancelConfirm && (
        <Dialog title="Descartar cotação?" onClose={() => setShowCancelConfirm(false)}>
          <div className="space-y-4">
            <p className="text-sm text-muted ">
              O rascunho atual será perdido. Deseja continuar?
            </p>
            <div className="flex gap-2 justify-end">
              <Button type="button" variant="outline" size="sm" onClick={() => setShowCancelConfirm(false)}>
                Continuar editando
              </Button>
              <Button type="button" size="sm" variant="destructive" onClick={confirmDiscard}>
                Descartar
              </Button>
            </div>
          </div>
        </Dialog>
      )}

      <p className="text-xs text-muted mb-3" role="status">{saveStatus} · Alt + ← para voltar</p>
      {insurersError && <p role="alert" className="text-danger">{insurersError}</p>}
      {recotarError && (
        <div className="mb-4 text-sm text-warning bg-canvas border border-line rounded px-4 py-3">
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
                  ? "control-primary border-line"
                  : "bg-surface text-ink border-line hover:border-line"
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
                    s <= step ? "bg-action" : "bg-surface "
                  }`}
                />
              </div>
            );
          })}
        </div>
        <p className="text-xs text-muted ">
          Passo {step} de 5 — {STEP_LABELS[step - 1]}
        </p>
      </div>

      <div id="quotation-step" className="bg-surface rounded border border-line p-4">
        {step === 1 && (
          <Step1
            dominios={dominios}
            defaultValues={step1Data}
            onNext={handleStep1}
          />
        )}

        {(step === 2 || step === 3) && ramo === "auto" && (
          <Step2Auto
            key={step}
            stage={step === 2 ? "object" : "profile"}
            defaultValues={step2Data}
            onBack={() => setStep(step - 1)}
            onNext={step === 2 ? handleStep2 : handleStep3}
          />
        )}

        {(step === 2 || step === 3) && ramo === "moto" && (
          <Step2Moto
            key={step}
            stage={step === 2 ? "object" : "profile"}
            defaultValues={step2Data}
            onBack={() => setStep(step - 1)}
            onNext={step === 2 ? handleStep2 : handleStep3}
          />
        )}

        {(step === 2 || step === 3) && ramo === "imovel" && (
          <Step2Imovel
            key={step}
            stage={step === 2 ? "object" : "profile"}
            dominios={dominios}
            defaultValues={step2Data}
            onBack={() => setStep(step - 1)}
            onNext={step === 2 ? handleStep2 : handleStep3}
          />
        )}

        {step === 4 && (
          <Step4
            ramo={ramo}
            coberturasIniciais={step3Data?.coberturas}
            seguradoras={insurers.filter(item => item.ramos.includes(ramo))}
            selecionadas={selectedInsurers}
            onSelecionadas={setSelectedInsurers}
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
            {cotacaoErrMsg && <p role="alert" className="text-sm text-danger">{cotacaoErrMsg}</p>}
            {polling && !pollCancelled && (
              <div className="flex items-center justify-between gap-3"><p className="text-xs text-muted tabular-nums">Consultas em andamento · {pollingSeconds}s</p><Button variant="outline" onClick={() => void handleCancel()}>Cancelar todas as consultas</Button></div>
            )}

            {pollCancelled && (
              <div className="text-sm text-muted bg-canvas rounded p-4">
                Acompanhamento pausado. A consulta continua no servidor.{" "}
                <button
                  type="button"
                  className="text-action underline"
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
                onCancel={cia => void handleCancel(cia)}
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
