import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/infrastructure/api/client";
import { useToast } from "@/presentation/components/ui/toast/ToastContext";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { IconTarget, IconCheck, IconInfo } from "@/presentation/components/ui/Icons";

// ─── Tipos ──────────────────────────────────────────────────────────────────

interface PickInput {
  market: string;
  outcome: string;
  target_value?: string | null;
  market_odd?: number | null;
}

interface BetAlert {
  level: string;
  code: string;
  title: string;
  message: string;
  suggestion: string;
}

interface SimulationResult {
  is_valid: boolean;
  score: number;
  recommendation: string;
  ev_estimate: number;
  potential_return: number;
  risk_level: string;
  alerts: BetAlert[];
}

interface SimulateResponse {
  error: string | null;
  result: SimulationResult | null;
  message: string;
}

// Tipo para mercado do market_scan
interface MarketEdge {
  market: string;
  outcome: string;
  label: string;
  model_prob: number;
  market_odd: number;
  implied_prob: number;
  expected_value: number;
  edge_pp: number;
  suggested_stake_pct: number;
  suggested_stake_value: number;
  meets_threshold: boolean;
  score_context?: string;
}

// Tipo para resposta do advice (simplificado)
interface LiveAdviceResponse {
  home_team: string;
  away_team: string;
  minute: number;
  current_score: string | null;
  is_live: boolean;
  is_finished: boolean;
  period_label: string | null;
  status: string | null;
  superbet_stale: boolean;
  h2h_odds: Record<string, number>;
  btts_odds: Record<string, number>;
  next_goal_odds: Record<string, number>;
  strategy: {
    market_scan?: MarketEdge[];
    opportunities?: MarketEdge[];
  } | null;
  captured_at: string | null;
}

// ─── Formatadores ───────────────────────────────────────────────────────────

function formatBRL(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
  }).format(value);
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-400";
  if (score >= 45) return "text-yellow-400";
  return "text-red-400";
}

function scoreBg(score: number): string {
  if (score >= 70) return "bg-emerald-500/10 border-emerald-500/30";
  if (score >= 45) return "bg-yellow-500/10 border-yellow-500/30";
  return "bg-red-500/10 border-red-500/30";
}

function alertIcon(level: string) {
  switch (level) {
    case "critical": return <span className="text-red-400 text-lg">⚠️</span>;
    case "warning": return <span className="text-yellow-400 text-lg">⚠️</span>;
    case "success": return <IconCheck className="h-5 w-5 text-emerald-400" />;
    case "info": return <IconInfo className="h-5 w-5 text-blue-400" />;
    default: return <IconInfo className="h-5 w-5 text-slate-400" />;
  }
}

function alertBorder(level: string): string {
  switch (level) {
    case "critical": return "border-red-500/30 bg-red-500/5";
    case "warning": return "border-yellow-500/30 bg-yellow-500/5";
    case "success": return "border-emerald-500/30 bg-emerald-500/5";
    case "info": return "border-blue-500/30 bg-blue-500/5";
    default: return "border-slate-500/30 bg-slate-500/5";
  }
}

function evColor(ev: number): string {
  if (ev >= 0.15) return "text-emerald-400";
  if (ev >= 0.08) return "text-emerald-300";
  if (ev >= 0.03) return "text-yellow-400";
  if (ev > 0) return "text-yellow-300";
  return "text-red-400";
}

// ─── Componentes auxiliares ─────────────────────────────────────────────────

function AlertCard({ alert }: { alert: BetAlert }) {
  return (
    <div className={`rounded-xl border p-4 ${alertBorder(alert.level)}`}>
      <div className="flex items-start gap-3">
        <div className="shrink-0 mt-0.5">{alertIcon(alert.level)}</div>
        <div className="flex-1 min-w-0">
          <h4 className={`text-sm font-bold ${
            alert.level === "critical" ? "text-red-400" :
            alert.level === "warning" ? "text-yellow-400" :
            alert.level === "success" ? "text-emerald-400" :
            "text-blue-400"
          }`}>
            {alert.title}
          </h4>
          <p className="text-xs text-slate-300 mt-1 leading-relaxed">{alert.message}</p>
          {alert.suggestion && (
            <div className="mt-2 text-xs text-slate-400 bg-white/5 rounded-lg px-3 py-2">
              <span className="font-semibold text-slate-300">💡 Dica:</span> {alert.suggestion}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ScoreGauge({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  let color = "#ef4444";
  if (pct >= 70) color = "#10b981";
  else if (pct >= 45) color = "#f59e0b";
  else if (pct >= 25) color = "#f97316";

  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (pct / 100) * circumference;

  return (
    <div className="flex flex-col items-center">
      <svg width="120" height="120" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="45" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="8" />
        <circle
          cx="60"
          cy="60"
          r="45"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          transform="rotate(-90 60 60)"
          style={{ transition: "stroke-dashoffset 0.5s ease" }}
        />
        <text x="60" y="58" textAnchor="middle" fill="white" fontSize="22" fontWeight="bold">
          {score.toFixed(0)}
        </text>
        <text x="60" y="74" textAnchor="middle" fill="#94a3b8" fontSize="10">
          / 100
        </text>
      </svg>
    </div>
  );
}

// ─── Mapeamento de mercados para o simulador ───────────────────────────────

const MARKET_OPTIONS = [
  { value: "h2h", label: "1X2", outcomes: ["1", "X", "2"] },
  { value: "totals", label: "Total Gols", outcomes: ["over", "under"] },
  { value: "btts", label: "Ambos Marcam", outcomes: ["yes", "no"] },
  { value: "next_goal", label: "Próximo Gol", outcomes: ["home", "away", "none"] },
  { value: "handicap", label: "Handicap", outcomes: ["home", "away"] },
  { value: "other", label: "Outro", outcomes: [] },
];

function findMarketEdge(marketScan: MarketEdge[], market: string, outcome: string): MarketEdge | undefined {
  // Tenta match exato primeiro
  let edge = marketScan.find(e => e.market === market && e.outcome === outcome);
  if (edge) return edge;
  // Tenta match parcial
  edge = marketScan.find(e => e.market === market && e.outcome.toLowerCase() === outcome.toLowerCase());
  if (edge) return edge;
  // Para h2h, tenta mapear 1/X/2
  if (market === "h2h") {
    const map: Record<string, string> = { "1": "home", "x": "home", "2": "away" };
    edge = marketScan.find(e => e.market === "h2h" && e.outcome === map[outcome.toLowerCase()]);
  }
  return edge;
}

function filterMarketScanByType(marketScan: MarketEdge[], currentMarket: string): MarketEdge[] {
  if (currentMarket === "h2h") return marketScan.filter(e => e.market === "h2h");
  if (currentMarket === "totals") return marketScan.filter(e => e.market.includes("over") || e.market.includes("under"));
  if (currentMarket === "btts") return marketScan.filter(e => e.market === "btts");
  if (currentMarket === "next_goal") return marketScan.filter(e => e.market === "next_goal");
  if (currentMarket === "handicap") return marketScan.filter(e => e.market.includes("handicap"));
  return marketScan;
}

// ─── Página Principal ───────────────────────────────────────────────────────

export function BetSimulatorPage() {
  const { addToast } = useToast();

  // Form state
  const [eventName, setEventName] = useState("");
  const [homeTeam, setHomeTeam] = useState("");
  const [awayTeam, setAwayTeam] = useState("");
  const [stake, setStake] = useState("10");
  const [oddsPlaced, setOddsPlaced] = useState("");
  const [minute, setMinute] = useState("");
  const [superbetEventId, setSuperbetEventId] = useState("");
  const [picks, setPicks] = useState<PickInput[]>([
    { market: "h2h", outcome: "", market_odd: undefined },
  ]);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [marketScan, setMarketScan] = useState<MarketEdge[]>([]);
  const [showMarketPicker, setShowMarketPicker] = useState(false);
  const [activePickIndex, setActivePickIndex] = useState<number | null>(null);

  // ── Busca dados do evento quando ID muda ──────────────────────────────
  const eventQuery = useQuery({
    queryKey: ["superbet-event", superbetEventId],
    queryFn: async (): Promise<LiveAdviceResponse> => {
      const id = parseInt(superbetEventId);
      if (!id || isNaN(id)) throw new Error("ID inválido");
      return apiFetch<LiveAdviceResponse>(`/worldcup/superbet/live/${id}/advice?fast=true`, {
        method: "GET",
      });
    },
    enabled: !!superbetEventId && parseInt(superbetEventId) > 0 && superbetEventId.length >= 5,
    staleTime: 30000, // 30s cache
    retry: 1,
  });

  // Atualiza formulário quando dados chegam
  useEffect(() => {
    if (eventQuery.data && !eventQuery.isError) {
      const data = eventQuery.data;
      // Preenche times
      if (data.home_team && !homeTeam) setHomeTeam(data.home_team);
      if (data.away_team && !awayTeam) setAwayTeam(data.away_team);
      // Preenche nome do evento
      if (data.home_team && data.away_team && !eventName) {
        setEventName(`${data.home_team} x ${data.away_team}`);
      }
      // Preenche minuto
      if (data.minute && !minute) {
        setMinute(data.minute.toString());
      }
      // Guarda market scan
      if (data.strategy?.market_scan) {
        setMarketScan(data.strategy.market_scan);
      }
      // Toast informativo
      if (data.is_live) {
        addToast(
          `📡 ${data.home_team} x ${data.away_team} — ${data.minute}' (${data.current_score})`,
          "success"
        );
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventQuery.data]);

  // ── Simulação ─────────────────────────────────────────────────────────
  const simulateMutation = useMutation({
    mutationFn: async (): Promise<SimulateResponse> => {
      const payload = {
        event_name: eventName,
        home_team: homeTeam,
        away_team: awayTeam,
        stake: parseFloat(stake) || 0,
        odds_placed: parseFloat(oddsPlaced) || 1,
        potential_return: (parseFloat(stake) || 0) * (parseFloat(oddsPlaced) || 1),
        picks: picks.filter((p) => p.market && p.outcome).map((p) => ({
          market: p.market,
          outcome: p.outcome,
          target_value: p.target_value || null,
          market_odd: p.market_odd || null,
        })),
        minute: minute ? parseInt(minute) : null,
        superbet_event_id: superbetEventId ? parseInt(superbetEventId) : null,
        source: "manual",
      };
      return apiFetch<SimulateResponse>("/user/bets/simulate", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: (data) => {
      if (data.result) {
        setResult(data.result);
        const criticalCount = data.result.alerts.filter((a) => a.level === "critical").length;
        const warningCount = data.result.alerts.filter((a) => a.level === "warning").length;

        if (data.result.recommendation === "STOP") {
          addToast(
            `🛑 Score ${data.result.score}/100 — NÃO APOSTE! ${criticalCount} erro(s) crítico(s)`,
            "error"
          );
        } else if (data.result.recommendation === "CAUTION") {
          addToast(
            `⚠️ Score ${data.result.score}/100 — Cuidado! ${warningCount} alerta(s)`,
            "error"
          );
        } else {
          addToast(
            `✅ Score ${data.result.score}/100 — Aposta aprovada!`,
            "success"
          );
        }
      }
    },
    onError: (err: Error) => {
      addToast(`Erro na simulação: ${err.message}`, "error");
    },
  });

  // ── Helpers para picks ────────────────────────────────────────────────
  const addPick = () => {
    setPicks([...picks, { market: "h2h", outcome: "" }]);
  };

  const removePick = (idx: number) => {
    if (picks.length <= 1) return;
    setPicks(picks.filter((_, i) => i !== idx));
  };

  const updatePick = (idx: number, field: keyof PickInput, value: string | number | null) => {
    const updated = [...picks];
    updated[idx] = { ...updated[idx], [field]: value };
    setPicks(updated);
  };

  const autoFillOdd = (idx: number, market: string, outcome: string) => {
    if (!marketScan.length) return;
    const edge = findMarketEdge(marketScan, market, outcome);
    if (edge) {
      updatePick(idx, "market_odd", edge.market_odd);
    }
  };

  const openMarketPicker = (idx: number) => {
    setActivePickIndex(idx);
    setShowMarketPicker(true);
  };

  const selectMarketOption = (market: string, outcome: string) => {
    if (activePickIndex === null) return;
    updatePick(activePickIndex, "market", market);
    updatePick(activePickIndex, "outcome", outcome);
    // Auto-preenche odd se tiver market_scan
    autoFillOdd(activePickIndex, market, outcome);
    setShowMarketPicker(false);
    setActivePickIndex(null);
  };

  // Calcula odd total automaticamente
  useEffect(() => {
    const validPicks = picks.filter(p => p.market_odd && p.market_odd > 1);
    if (validPicks.length > 0) {
      const totalOdd = validPicks.reduce((acc, p) => acc * (p.market_odd || 1), 1);
      setOddsPlaced(totalOdd.toFixed(2));
    }
  }, [picks]);

  const canSimulate = eventName && homeTeam && awayTeam && stake && oddsPlaced && picks.some((p) => p.market && p.outcome);

  // ── Render ────────────────────────────────────────────────────────────
  return (
    <PageTransition>
      <div className="space-y-4 max-w-3xl mx-auto">
        <PageHeader
          title="🧪 Simulador de Apostas"
          subtitle="Teste sua aposta antes de colocar na Superbet. Detectamos padrões de perda automaticamente."
        />

        {/* Formulário */}
        <div className="live-glass-panel p-5 space-y-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <IconTarget className="h-4 w-4 text-emerald-400" />
            Monte seu bilhete
          </h3>

          {/* Evento + ID Superbet */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Evento</label>
              <input
                type="text"
                value={eventName}
                onChange={(e) => setEventName(e.target.value)}
                placeholder="Ex: Brasil x Argentina"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-emerald-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1 flex items-center gap-2">
                ID Superbet
                {eventQuery.isLoading && (
                  <span className="inline-block h-3 w-3 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                )}
                {eventQuery.isSuccess && <span className="text-emerald-400">✓</span>}
                {eventQuery.isError && <span className="text-red-400">✗</span>}
              </label>
              <input
                type="text"
                value={superbetEventId}
                onChange={(e) => {
                  setSuperbetEventId(e.target.value);
                  // Limpa dados antigos se apagar
                  if (!e.target.value) {
                    setMarketScan([]);
                  }
                }}
                placeholder="Ex: 13127506 (auto-preenche dados)"
                className={`w-full rounded-lg border px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none transition-colors ${
                  eventQuery.isSuccess
                    ? "border-emerald-500/50 bg-emerald-500/5"
                    : eventQuery.isError
                    ? "border-red-500/50 bg-red-500/5"
                    : "border-white/10 bg-white/5 focus:border-emerald-500/50"
                }`}
              />
              {eventQuery.isError && (
                <p className="text-xs text-red-400 mt-1">
                  Erro ao buscar evento: {eventQuery.error?.message || "Verifique o ID"}
                </p>
              )}
            </div>
          </div>

          {/* Info ao vivo (quando tem dados) */}
          {eventQuery.data?.is_live && (
            <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3 flex items-center gap-3">
              <div className="text-lg">📡</div>
              <div className="flex-1">
                <div className="text-sm font-semibold text-emerald-400">
                  {eventQuery.data.home_team} {eventQuery.data.current_score} {eventQuery.data.away_team}
                </div>
                <div className="text-xs text-slate-400">
                  {eventQuery.data.minute}' · {eventQuery.data.period_label || "Ao vivo"}
                  {eventQuery.data.superbet_stale && " · (dados em cache)"}
                </div>
              </div>
              <div className="text-xs text-slate-500">
                {marketScan.length} mercados disponíveis
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Mandante</label>
              <input
                type="text"
                value={homeTeam}
                onChange={(e) => setHomeTeam(e.target.value)}
                placeholder="Ex: Brasil"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-emerald-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Visitante</label>
              <input
                type="text"
                value={awayTeam}
                onChange={(e) => setAwayTeam(e.target.value)}
                placeholder="Ex: Argentina"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-emerald-500/50 focus:outline-none"
              />
            </div>
          </div>

          {/* Pernas */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs text-slate-400">Pernas do bilhete</label>
              <div className="flex items-center gap-2">
                {marketScan.length > 0 && (
                  <span className="text-xs text-emerald-400">
                    {marketScan.filter(m => m.meets_threshold).length} oportunidades
                  </span>
                )}
                <button
                  onClick={addPick}
                  className="text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition-colors"
                >
                  <span className="text-lg">+</span> Adicionar perna
                </button>
              </div>
            </div>

            {picks.map((pick, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <select
                  value={pick.market}
                  onChange={(e) => {
                    updatePick(idx, "market", e.target.value);
                    updatePick(idx, "outcome", "");
                    updatePick(idx, "market_odd", null);
                  }}
                  className="rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-sm text-white focus:border-emerald-500/50 focus:outline-none"
                >
                  {MARKET_OPTIONS.map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>

                {/* Input de palpite com picker */}
                <div className="flex-1 relative">
                  <input
                    type="text"
                    value={pick.outcome}
                    onChange={(e) => {
                      updatePick(idx, "outcome", e.target.value);
                      autoFillOdd(idx, pick.market, e.target.value);
                    }}
                    placeholder="Palpite (1, X, 2, over, under...)"
                    className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-emerald-500/50 focus:outline-none"
                  />
                  {/* Badge de odd auto-preenchida */}
                  {pick.market_odd && (
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-emerald-400">
                      @{pick.market_odd}
                    </div>
                  )}
                </div>

                {/* Botão de picker (quando tem market_scan) */}
                {marketScan.length > 0 && (
                  <button
                    onClick={() => openMarketPicker(idx)}
                    className="text-xs bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-2 py-2 rounded-lg hover:bg-emerald-500/20 transition-colors"
                    title="Ver palpites disponíveis com odds"
                  >
                    📋
                  </button>
                )}

                <input
                  type="number"
                  step="0.01"
                  value={pick.market_odd || ""}
                  onChange={(e) => updatePick(idx, "market_odd", e.target.value ? parseFloat(e.target.value) : null)}
                  placeholder="Odd"
                  className="w-20 rounded-lg border border-white/10 bg-white/5 px-2 py-2 text-sm text-white placeholder:text-slate-600 focus:border-emerald-500/50 focus:outline-none"
                />
                {picks.length > 1 && (
                  <button
                    onClick={() => removePick(idx)}
                    className="text-red-400 hover:text-red-300 transition-colors"
                  >
                    <span className="text-lg">🗑</span>
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Stake / Odd / Minuto */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Stake (R$)</label>
              <input
                type="number"
                step="0.01"
                value={stake}
                onChange={(e) => setStake(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-emerald-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Odd Total</label>
              <input
                type="number"
                step="0.01"
                value={oddsPlaced}
                onChange={(e) => setOddsPlaced(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white focus:border-emerald-500/50 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Minuto (opcional)</label>
              <input
                type="number"
                value={minute}
                onChange={(e) => setMinute(e.target.value)}
                placeholder="Ex: 67"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:border-emerald-500/50 focus:outline-none"
              />
            </div>
          </div>

          {/* Retorno estimado */}
          {stake && oddsPlaced && (
            <div className="flex items-center justify-between text-sm bg-white/5 rounded-lg px-3 py-2">
              <span className="text-slate-400">Retorno potencial:</span>
              <span className="text-emerald-400 font-bold">
                {formatBRL((parseFloat(stake) || 0) * (parseFloat(oddsPlaced) || 0))}
              </span>
            </div>
          )}

          {/* Botão Simular */}
          <button
            onClick={() => simulateMutation.mutate()}
            disabled={!canSimulate || simulateMutation.isPending}
            className="w-full rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 font-semibold py-3 hover:bg-emerald-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {simulateMutation.isPending ? "Analisando..." : "🔍 Simular Aposta"}
          </button>
        </div>

        {/* Modal de seleção de mercados */}
        {showMarketPicker && activePickIndex !== null && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="live-glass-panel-glow max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-xl">
              <div className="p-4 border-b border-white/8 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-white">
                  📋 Palpites disponíveis — {MARKET_OPTIONS.find(m => m.value === picks[activePickIndex]?.market)?.label}
                </h3>
                <button
                  onClick={() => { setShowMarketPicker(false); setActivePickIndex(null); }}
                  className="text-slate-400 hover:text-white"
                >
                  ✕
                </button>
              </div>
              <div className="p-4 space-y-2">
                {filterMarketScanByType(marketScan, picks[activePickIndex]?.market || "")
                  .sort((a, b) => b.edge_pp - a.edge_pp)
                  .map((edge, i) => (
                    <button
                      key={i}
                      onClick={() => selectMarketOption(
                        picks[activePickIndex]?.market || "other",
                        edge.outcome
                      )}
                      className={`w-full text-left rounded-lg border p-3 transition-colors hover:bg-white/5 ${
                        edge.meets_threshold
                          ? "border-emerald-500/30 bg-emerald-500/5"
                          : "border-white/8 bg-black/25"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-semibold text-white">{edge.label}</div>
                          <div className="text-xs text-slate-400">
                            {edge.market} · {edge.outcome}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-bold text-white">@{edge.market_odd}</div>
                          <div className={`text-xs ${evColor(edge.expected_value)}`}>
                            EV {(edge.expected_value * 100).toFixed(1)}%
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 mt-2 text-xs">
                        <span className="text-slate-400">
                          Modelo: {(edge.model_prob * 100).toFixed(1)}%
                        </span>
                        <span className="text-slate-400">
                          Casa: {(edge.implied_prob * 100).toFixed(1)}%
                        </span>
                        <span className={`font-semibold ${edge.edge_pp > 0 ? "text-emerald-400" : "text-red-400"}`}>
                          Edge {edge.edge_pp > 0 ? "+" : ""}{edge.edge_pp.toFixed(1)}pp
                        </span>
                        {edge.meets_threshold && (
                          <span className="text-emerald-400 font-semibold">✓ Oportunidade</span>
                        )}
                      </div>
                    </button>
                  ))}
                {filterMarketScanByType(marketScan, picks[activePickIndex]?.market || "").length === 0 && (
                  <div className="text-center text-slate-400 text-sm py-8">
                    Nenhum mercado disponível para {MARKET_OPTIONS.find(m => m.value === picks[activePickIndex]?.market)?.label}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Resultado */}
        {result && (
          <div className="space-y-4">
            {/* Score Card */}
            <div className={`rounded-xl border p-5 ${scoreBg(result.score)}`}>
              <div className="flex items-center gap-5">
                <ScoreGauge score={result.score} />
                <div className="flex-1">
                  <div className={`text-2xl font-bold ${scoreColor(result.score)}`}>
                    {result.recommendation === "GO" && "✅ APOSTA APROVADA"}
                    {result.recommendation === "CAUTION" && "⚠️ CUIDADO — RESSALVAS"}
                    {result.recommendation === "STOP" && "🛑 NÃO APOSTE"}
                  </div>
                  <div className="text-sm text-slate-400 mt-1">
                    Score: <span className={`font-bold ${scoreColor(result.score)}`}>{result.score}/100</span>
                    {" · "}
                    EV estimado: {result.ev_estimate >= 0 ? "+" : ""}{(result.ev_estimate * 100).toFixed(1)}%
                    {" · "}
                    Risco: <span className="capitalize">{result.risk_level}</span>
                  </div>
                  {!result.is_valid && (
                    <div className="mt-2 text-sm text-red-400 font-bold">
                      ⚠️ Aposta inválida — corriga os erros antes de prosseguir
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Alertas */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-white">
                Alertas ({result.alerts.length})
              </h3>
              {result.alerts.map((alert, i) => (
                <AlertCard key={`${alert.code}-${i}`} alert={alert} />
              ))}
            </div>

            {/* Resumo rápido */}
            <div className="live-glass-panel p-4">
              <h4 className="text-sm font-semibold text-white mb-3">Resumo da Análise</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <div className="text-slate-500">Score</div>
                  <div className={`text-lg font-bold ${scoreColor(result.score)}`}>{result.score}</div>
                </div>
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <div className="text-slate-500">EV</div>
                  <div className={`text-lg font-bold ${result.ev_estimate >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {result.ev_estimate >= 0 ? "+" : ""}{(result.ev_estimate * 100).toFixed(1)}%
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <div className="text-slate-500">Retorno</div>
                  <div className="text-lg font-bold text-emerald-400">
                    {formatBRL(result.potential_return)}
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <div className="text-slate-500">Risco</div>
                  <div className={`text-lg font-bold capitalize ${
                    result.risk_level === "low" ? "text-emerald-400" :
                    result.risk_level === "medium" ? "text-yellow-400" :
                    "text-red-400"
                  }`}>
                    {result.risk_level}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </PageTransition>
  );
}
