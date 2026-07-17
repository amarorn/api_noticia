import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { apiFetch } from "@/infrastructure/api/client";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { LiveDashboardTabs } from "@/presentation/components/live-dashboard/LiveDashboardTabs";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { teamColor } from "@/data/teamColors";
import { useTicket, type TicketLeg } from "@/presentation/hooks/useTicket";
import { TicketSimulator, AddBtn, confBadge, kickoffTime, FloatingTicketBadge } from "@/presentation/components/ticket/TicketSimulator";

// ── Types ─────────────────────────────────────────────────────────────────────

interface TodayMatch {
  id: string;
  home_team: string;
  away_team: string;
  kickoff_utc: string;
  kickoff_local: string;
  kickoff_date: string;
  group: string | null;
  phase: string;
  played: boolean;
  home_score?: number | null;
  away_score?: number | null;
  prob_home: number;
  prob_draw: number;
  prob_away: number;
  prediction: string;
  confidence: number;
  poisson_score: string;
  expected_goals: string;
}

interface TodayResponse {
  date: string;
  end_date: string;
  total: number;
  matches: TodayMatch[];
  next_match?: {
    home_team: string;
    away_team: string;
    kickoff_br?: string | null;
    eta_label?: string | null;
    phase?: string | null;
  } | null;
}

interface Pick {
  market: string;
  label: string;
  model_prob: number;
  fair_odd: number | null;
  kelly_units: number;
  confidence: string;
}

interface ComboTicket {
  label: string;
  markets: string[];
  model_prob: number;
  fair_odd: number | null;
  kelly_units: number;
  confidence: string;
}

interface AnalysisResponse {
  home_team: string;
  away_team: string;
  phase: string;
  group: string | null;
  prediction: string;
  confidence: number;
  prob_home: number;
  prob_draw: number;
  prob_away: number;
  poisson_score: string;
  expected_goals: string;
  h2h_summary: string;
  top_scorelines: { score: string; prob: number }[];
  picks: Pick[];
  ticket: { singles: Pick[]; combo: ComboTicket | null; note: string };
}

// ── Live picks types ──────────────────────────────────────────────────────────

interface LivePick {
  event_id: number;
  home: string;
  away: string;
  minute: number;
  score: string;
  market: string;
  outcome: string;
  label: string;
  model_prob: number;
  market_odd: number;
  fair_odd: number | null;
  ev_pct: number;
  edge_pp: number;
  kelly_quarter: number;
  suggested_stake_value: number | null;
  confidence_score: number;
  confidence_label: string;
  from_cache: boolean;
  captured_at: string;
}

interface LiveBestPicksResponse {
  count: number;
  games_analyzed: number;
  captured_at: string;
  picks: LivePick[];
}

// ── Live picks hook ───────────────────────────────────────────────────────────

function useLivePicks(minEv = 0.04) {
  return useQuery<LiveBestPicksResponse>({
    queryKey: ["live-best-picks", minEv],
    queryFn: () =>
      apiFetch<LiveBestPicksResponse>(
        `/worldcup/superbet/live/best-picks?compute_missing=false&min_ev=${minEv}&min_confidence=0.0&max_picks_per_game=4`
      ),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
    refetchIntervalInBackground: false,
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function legId(market: string, home: string, away: string) {
  return `${market}|${home}|${away}`;
}

// ── Mini probability donut ────────────────────────────────────────────────────

function ProbDonut({ home, draw, away }: { home: number; draw: number; away: number }) {
  const r = 26, cx = 32, cy = 32, stroke = 7;
  const circ = 2 * Math.PI * r;
  const hArc = circ * home;
  const dArc = circ * draw;
  const aArc = circ * away;
  return (
    <svg width={64} height={64} viewBox="0 0 64 64" className="shrink-0">
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e293b" strokeWidth={stroke} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#3b82f6" strokeWidth={stroke}
        strokeDasharray={`${hArc} ${circ}`} strokeDashoffset={0}
        transform={`rotate(-90 ${cx} ${cy})`} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#6b7280" strokeWidth={stroke}
        strokeDasharray={`${dArc} ${circ}`} strokeDashoffset={-hArc}
        transform={`rotate(-90 ${cx} ${cy})`} />
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#f97316" strokeWidth={stroke}
        strokeDasharray={`${aArc} ${circ}`} strokeDashoffset={-(hArc + dArc)}
        transform={`rotate(-90 ${cx} ${cy})`} />
      <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle"
        fill="white" fontSize="9" fontWeight="bold">
        {Math.round(Math.max(home, draw, away) * 100)}%
      </text>
    </svg>
  );
}

// ── Prob bar ─────────────────────────────────────────────────────────────────

function ProbBar3({ home, draw, away, homeTeam, awayTeam }: {
  home: number; draw: number; away: number; homeTeam: string; awayTeam: string;
}) {
  const hp = Math.round(home * 100);
  const dp = Math.round(draw * 100);
  const ap = Math.round(away * 100);
  return (
    <div className="space-y-1.5">
      <div className="flex h-7 rounded-lg overflow-hidden text-[11px] font-bold">
        <div className="flex items-center justify-center bg-blue-600/80 text-white" style={{ width: `${hp}%` }}>
          {hp > 12 ? `${hp}%` : ""}
        </div>
        <div className="flex items-center justify-center bg-slate-600/70 text-white" style={{ width: `${dp}%` }}>
          {dp > 10 ? `${dp}%` : ""}
        </div>
        <div className="flex items-center justify-center bg-orange-500/80 text-white" style={{ width: `${ap}%` }}>
          {ap > 12 ? `${ap}%` : ""}
        </div>
      </div>
      <div className="flex justify-between text-[10px] text-slate-500">
        <span className="text-blue-400 font-semibold truncate max-w-[35%]">{homeTeam}</span>
        <span>X</span>
        <span className="text-orange-400 font-semibold truncate max-w-[35%] text-right">{awayTeam}</span>
      </div>
    </div>
  );
}

// ── ECharts: All-games overview ───────────────────────────────────────────────

function GamesOverviewChart({ matches }: { matches: TodayMatch[] }) {
  const upcoming = matches.filter(m => !m.played);
  if (upcoming.length === 0) return null;

  const labels = upcoming.map(m => `${m.home_team.split(" ")[0]} x ${m.away_team.split(" ")[0]}`);
  const option: EChartsOption = {
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" },
      backgroundColor: "#0f172a", borderColor: "#334155", textStyle: { color: "#e2e8f0", fontSize: 12 } },
    legend: { data: ["Casa", "Empate", "Fora"], textStyle: { color: "#94a3b8", fontSize: 11 }, top: 4 },
    grid: { left: 12, right: 12, top: 36, bottom: 4, containLabel: true },
    xAxis: { type: "value", max: 100,
      axisLabel: { color: "#475569", fontSize: 10, formatter: "{value}%" },
      splitLine: { lineStyle: { color: "#1e293b" } } },
    yAxis: { type: "category", data: labels,
      axisLabel: { color: "#94a3b8", fontSize: 11, width: 100, overflow: "truncate" },
      axisTick: { show: false }, axisLine: { lineStyle: { color: "#1e293b" } } },
    series: [
      { name: "Casa", type: "bar", stack: "total",
        data: upcoming.map(m => +(m.prob_home * 100).toFixed(1)),
        itemStyle: { color: "#3b82f6", borderRadius: [4, 0, 0, 4] }, barMaxWidth: 28 },
      { name: "Empate", type: "bar", stack: "total",
        data: upcoming.map(m => +(m.prob_draw * 100).toFixed(1)),
        itemStyle: { color: "#4b5563" } },
      { name: "Fora", type: "bar", stack: "total",
        data: upcoming.map(m => +(m.prob_away * 100).toFixed(1)),
        itemStyle: { color: "#f97316", borderRadius: [0, 4, 4, 0] } },
    ],
  };
  return <ReactECharts option={option} style={{ height: Math.max(180, upcoming.length * 52) }} theme="dark" />;
}

// ── Confidence gauge ──────────────────────────────────────────────────────────

function ConfidenceGauge({ value, label }: { value: number; label: string }) {
  const color = value >= 0.65 ? "#10b981" : value >= 0.50 ? "#3b82f6" : "#f97316";
  const option: EChartsOption = {
    backgroundColor: "transparent",
    series: [{
      type: "gauge", startAngle: 200, endAngle: -20, min: 0, max: 100,
      progress: { show: true, width: 8, itemStyle: { color } },
      axisLine: { lineStyle: { width: 8, color: [[1, "#1e293b"]] } },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
      pointer: { show: false }, anchor: { show: false },
      detail: { offsetCenter: [0, "8%"], fontSize: 18, fontWeight: "bold", color: "#fff", formatter: "{value}%" },
      title: { offsetCenter: [0, "60%"], fontSize: 10, color: "#64748b" },
      data: [{ value: Math.round(value * 100), name: label }],
    }],
  };
  return <ReactECharts option={option} style={{ height: 120 }} theme="dark" />;
}

// ── Ticket Simulator wrapper (converte analyses → suggestions) ────────────────

function CentralTicketSimulator({
  ticket, analyses,
}: {
  ticket: ReturnType<typeof useTicket>;
  analyses: (AnalysisResponse & { kickoff: string })[];
}) {
  const suggestions = useMemo((): TicketLeg[] => {
    const list: TicketLeg[] = [];
    for (const a of analyses) {
      const kickoff = a.kickoff ?? "";
      for (const s of a.ticket.singles) {
        if (!s.fair_odd) continue;
        list.push({
          id: legId(s.market, a.home_team, a.away_team),
          home: a.home_team, away: a.away_team, group: a.group, kickoff,
          label: s.label, market: s.market,
          fairOdd: s.fair_odd, modelProb: s.model_prob, confidence: s.confidence,
          type: "single",
        });
      }
      if (a.ticket.combo?.fair_odd) {
        const c = a.ticket.combo;
        list.push({
          id: legId("COMBO", a.home_team, a.away_team),
          home: a.home_team, away: a.away_team, group: a.group, kickoff,
          label: c.label, market: "COMBO",
          fairOdd: c.fair_odd!, modelProb: c.model_prob, confidence: c.confidence,
          type: "combo",
        });
      }
    }
    return list;
  }, [analyses]);

  return <TicketSimulator ticket={ticket} suggestions={suggestions} />;
}

// ── Best Tickets section ──────────────────────────────────────────────────────

interface BestBet {
  id: string;
  home: string;
  away: string;
  label: string;
  market: string;
  prob: number;
  fairOdd: number | null;
  kelly: number;
  confidence: string;
  type: "single" | "combo";
  group: string | null;
  kickoff: string;
}

function BestTicketsSection({
  analyses, ticket,
}: {
  analyses: (AnalysisResponse & { kickoff: string })[];
  ticket: ReturnType<typeof useTicket>;
}) {
  const bets = useMemo<BestBet[]>(() => {
    const all: BestBet[] = [];
    for (const a of analyses) {
      const top = a.ticket.singles[0];
      if (top) all.push({
        id: legId(top.market, a.home_team, a.away_team),
        home: a.home_team, away: a.away_team,
        label: top.label, market: top.market,
        prob: top.model_prob, fairOdd: top.fair_odd, kelly: top.kelly_units,
        confidence: top.confidence, type: "single", group: a.group, kickoff: a.kickoff,
      });
      if (a.ticket.combo) all.push({
        id: legId("COMBO", a.home_team, a.away_team),
        home: a.home_team, away: a.away_team,
        label: a.ticket.combo.label, market: "COMBO",
        prob: a.ticket.combo.model_prob, fairOdd: a.ticket.combo.fair_odd,
        kelly: a.ticket.combo.kelly_units, confidence: a.ticket.combo.confidence,
        type: "combo", group: a.group, kickoff: a.kickoff,
      });
    }
    return all.sort((a, b) => {
      if (a.type === "combo" && b.type !== "combo") return -1;
      if (b.type === "combo" && a.type !== "combo") return 1;
      const score = (x: BestBet) => x.prob + (x.confidence === "Alta" ? 0.3 : x.confidence === "Média" ? 0.15 : 0);
      return score(b) - score(a);
    }).slice(0, 6);
  }, [analyses]);

  const combos = bets.filter(b => b.type === "combo");
  const singles = bets.filter(b => b.type === "single");

  return (
    <div className="space-y-4">
      {combos.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-white">🏆 Apostas Combinadas</span>
            <span className="text-[10px] text-slate-500 bg-white/5 px-2 py-0.5 rounded-full">Maior retorno</span>
          </div>
          {combos.map((b, i) => <BetSlip key={b.id} bet={b} rank={i + 1} highlight ticket={ticket} />)}
        </div>
      )}
      {singles.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-white">🎯 Melhores Simples</span>
          </div>
          {singles.map((b, i) => <BetSlip key={b.id} bet={b} rank={i + 1} ticket={ticket} />)}
        </div>
      )}
    </div>
  );
}

function BetSlip({
  bet, rank, highlight = false, ticket,
}: {
  bet: BestBet; rank: number; highlight?: boolean; ticket: ReturnType<typeof useTicket>;
}) {
  const medal = rank === 1 ? "🥇" : rank === 1 ? "🥈" : rank === 3 ? "🥉" : `${rank}.`;
  const border = highlight
    ? "border-emerald-500/40 bg-gradient-to-r from-emerald-950/60 to-slate-900/60"
    : "border-white/10 bg-black/25";

  const leg: TicketLeg = {
    id: bet.id,
    home: bet.home, away: bet.away, group: bet.group, kickoff: bet.kickoff,
    label: bet.label, market: bet.market,
    fairOdd: bet.fairOdd ?? 1, modelProb: bet.prob, confidence: bet.confidence,
    type: bet.type,
  };

  return (
    <div className={`rounded-xl border ${border} p-4`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base shrink-0">{medal}</span>
          <div className="min-w-0">
            <div className="text-xs text-slate-400 truncate">
              {bet.home} × {bet.away}
              {bet.group && <span className="ml-1 text-emerald-500">· Gr.{bet.group}</span>}
            </div>
            <div className="text-[10px] text-slate-600">{kickoffTime(bet.kickoff)}</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {bet.type === "combo" && (
            <span className="text-[9px] font-bold bg-emerald-800/50 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-700/40">
              COMBO
            </span>
          )}
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${confBadge(bet.confidence)}`}>
            {bet.confidence}
          </span>
          {bet.fairOdd && <AddBtn leg={leg} ticket={ticket} />}
        </div>
      </div>

      <div className="text-sm font-bold text-white mb-3">{bet.label}</div>

      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "Odd Justa", val: bet.fairOdd?.toFixed(2) ?? "—", color: "text-emerald-300" },
          { label: "Prob. Modelo", val: `${(bet.prob * 100).toFixed(0)}%`, color: "text-blue-300" },
          { label: "Kelly 25%", val: `${bet.kelly.toFixed(1)}u`, color: "text-amber-300" },
        ].map(({ label, val, color }) => (
          <div key={label} className="rounded-lg bg-black/30 p-2 text-center">
            <div className="text-[10px] text-slate-500">{label}</div>
            <div className={`text-lg font-black font-mono ${color}`}>{val}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Game card ─────────────────────────────────────────────────────────────────

function GameCard({
  match, analysis, isSelected, onClick,
}: {
  match: TodayMatch; analysis?: AnalysisResponse; isSelected: boolean; onClick: () => void;
}) {
  const homeCol = teamColor(match.home_team);
  const awayCol = teamColor(match.away_team);
  return (
    <button onClick={onClick} className={`w-full text-left rounded-2xl border transition-all duration-200 ${
      isSelected
        ? "border-blue-500/60 bg-blue-950/30 shadow-lg shadow-blue-950/40"
        : match.played
        ? "border-white/8 bg-black/15 opacity-60 hover:opacity-80"
        : "border-white/8 bg-black/20 hover:border-neon-green/20 hover:bg-black/25"
    }`}>
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-1.5">
            {match.group && (
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-900/30 border border-emerald-700/30 px-2 py-0.5 rounded-full">
                Gr.{match.group}
              </span>
            )}
            {match.played
              ? <span className="text-[10px] text-slate-500 bg-white/5 px-2 py-0.5 rounded-full">Encerrado</span>
              : <span className="text-[10px] text-amber-400 font-semibold">{kickoffTime(match.kickoff_utc)}</span>
            }
          </div>
          <ProbDonut home={match.prob_home} draw={match.prob_draw} away={match.prob_away} />
        </div>

        <div className="flex items-center gap-2 mb-3">
          <div className="flex-1 min-w-0">
            <div className="font-bold text-sm truncate" style={{ color: homeCol }}>{match.home_team}</div>
          </div>
          {match.played
            ? <div className="text-xl font-black text-white font-mono shrink-0 px-2">{match.home_score ?? 0} – {match.away_score ?? 0}</div>
            : <div className="text-xs font-black text-slate-500 shrink-0 px-2">VS</div>
          }
          <div className="flex-1 min-w-0 text-right">
            <div className="font-bold text-sm truncate" style={{ color: awayCol }}>{match.away_team}</div>
          </div>
        </div>

        {!match.played && (
          <ProbBar3
            home={match.prob_home} draw={match.prob_draw} away={match.prob_away}
            homeTeam={match.home_team} awayTeam={match.away_team}
          />
        )}

        {!match.played && (
          <div className="flex items-center gap-2 mt-3">
            <span className="text-xs bg-white/5 text-slate-200 px-2 py-0.5 rounded-full font-semibold truncate">
              {match.prediction}
            </span>
            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${confBadge(
              match.confidence >= 0.65 ? "Alta" : match.confidence >= 0.5 ? "Média" : "Baixa"
            )}`}>
              {(match.confidence * 100).toFixed(0)}% conf.
            </span>
          </div>
        )}

        {analysis && !match.played && analysis.ticket.singles[0] && (
          <div className="mt-3 pt-3 border-t border-white/8">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500 shrink-0">🎯</span>
              <span className="text-xs text-white font-semibold truncate">
                {analysis.ticket.singles[0].label}
              </span>
              <span className="ml-auto text-xs text-emerald-300 font-mono shrink-0">
                {analysis.ticket.singles[0].fair_odd?.toFixed(2) ?? "—"}
              </span>
            </div>
          </div>
        )}
      </div>
    </button>
  );
}

// ── Expanded analysis ─────────────────────────────────────────────────────────

function ExpandedAnalysis({
  analysis, ticket,
}: {
  match: TodayMatch; analysis: AnalysisResponse; ticket: ReturnType<typeof useTicket>;
}) {
  const [activeTab, setActiveTab] = useState<"bilhete" | "placares" | "picks">("bilhete");

  const scoreChartOption: EChartsOption = useMemo(() => ({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", backgroundColor: "#0f172a", borderColor: "#334155",
      textStyle: { color: "#e2e8f0", fontSize: 11 } },
    grid: { left: 8, right: 8, top: 8, bottom: 8, containLabel: true },
    xAxis: { type: "category", data: analysis.top_scorelines.slice(0, 8).map(s => s.score),
      axisLabel: { color: "#64748b", fontSize: 10 }, axisLine: { lineStyle: { color: "#1e293b" } } },
    yAxis: { type: "value",
      axisLabel: { color: "#475569", fontSize: 9,
        formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
      splitLine: { lineStyle: { color: "#1e293b" } } },
    series: [{
      type: "bar",
      data: analysis.top_scorelines.slice(0, 8).map(s => s.prob),
      itemStyle: {
        color: (p: { dataIndex: number }) => {
          const score = analysis.top_scorelines[p.dataIndex]?.score ?? "";
          const [h, a] = score.split("-").map(Number);
          return h > a ? "#3b82f6" : h < a ? "#f97316" : "#6b7280";
        },
        borderRadius: [4, 4, 0, 0],
      },
      barMaxWidth: 36,
      label: { show: true, position: "top", color: "#64748b", fontSize: 9,
        formatter: (p: unknown) => `${(((p as { value?: number }).value ?? 0) * 100).toFixed(0)}%` },
    }],
  }), [analysis.top_scorelines]);

  const makePickLeg = (pick: Pick, type: "single" | "combo" = "single"): TicketLeg => ({
    id: legId(pick.market, analysis.home_team, analysis.away_team),
    home: analysis.home_team, away: analysis.away_team,
    group: analysis.group, kickoff: "",
    label: pick.label, market: pick.market,
    fairOdd: pick.fair_odd ?? 1, modelProb: pick.model_prob,
    confidence: pick.confidence, type,
  });

  return (
    <div className="rounded-2xl border border-blue-500/20 bg-blue-950/10 overflow-hidden">
      <div className="p-4 border-b border-white/8 bg-black/20">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="text-xs text-slate-500 mb-0.5">H2H</div>
            <div className="text-xs text-slate-400 line-clamp-2">{analysis.h2h_summary}</div>
          </div>
          <ConfidenceGauge value={analysis.confidence} label="Conf." />
        </div>
        <div className="mt-2 flex items-center gap-3 flex-wrap">
          <span className="text-xs font-semibold text-white bg-white/5 px-2 py-0.5 rounded-full">{analysis.prediction}</span>
          <span className="text-xs text-slate-400">xG <span className="text-white font-mono">{analysis.expected_goals}</span></span>
          <span className="text-xs text-slate-400">Poisson <span className="text-white font-mono">{analysis.poisson_score}</span></span>
        </div>
      </div>

      <div className="flex border-b border-white/8">
        {(["bilhete", "placares", "picks"] as const).map(t => (
          <button key={t} onClick={() => setActiveTab(t)}
            className={`flex-1 py-2.5 text-xs font-semibold transition-colors ${
              activeTab === t ? "text-blue-300 border-b-2 border-blue-500 bg-blue-900/10" : "text-slate-500 hover:text-slate-300"
            }`}>
            {t === "bilhete" ? "🎯 Bilhete" : t === "placares" ? "⚽ Placares" : "💰 Todos os Picks"}
          </button>
        ))}
      </div>

      <div className="p-4 space-y-3">
        {activeTab === "bilhete" && (
          <div className="space-y-3">
            {analysis.ticket.combo && analysis.ticket.combo.fair_odd && (
              <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/30 p-3">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div>
                    <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-0.5">Combo recomendado</div>
                    <div className="text-sm font-bold text-white">{analysis.ticket.combo.label}</div>
                  </div>
                  <AddBtn
                    leg={{
                      id: legId("COMBO", analysis.home_team, analysis.away_team),
                      home: analysis.home_team, away: analysis.away_team,
                      group: analysis.group, kickoff: "",
                      label: analysis.ticket.combo.label, market: "COMBO",
                      fairOdd: analysis.ticket.combo.fair_odd!, modelProb: analysis.ticket.combo.model_prob,
                      confidence: analysis.ticket.combo.confidence, type: "combo",
                    }}
                    ticket={ticket}
                  />
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { l: "Odd Justa", v: analysis.ticket.combo.fair_odd.toFixed(2), c: "text-emerald-300" },
                    { l: "Prob.", v: `${(analysis.ticket.combo.model_prob * 100).toFixed(0)}%`, c: "text-blue-300" },
                    { l: "Kelly", v: `${analysis.ticket.combo.kelly_units.toFixed(1)}u`, c: "text-amber-300" },
                  ].map(({ l, v, c }) => (
                    <div key={l} className="bg-black/30 rounded-lg p-2 text-center">
                      <div className="text-[10px] text-slate-500">{l}</div>
                      <div className={`text-base font-black font-mono ${c}`}>{v}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {analysis.ticket.singles.map((pick, i) => {
              const medal = i === 0 ? "🥇" : i === 1 ? "🥈" : "🥉";
              return (
                <div key={pick.market} className={`flex items-center gap-3 rounded-lg border p-3 ${confBadge(pick.confidence)}`}>
                  <span className="text-lg shrink-0">{medal}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-white truncate">{pick.label}</div>
                    <div className="text-[10px] text-slate-500">{pick.market}</div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-base font-black font-mono text-white">{pick.fair_odd?.toFixed(2) ?? "—"}</div>
                    <div className="text-[10px] text-slate-400">{(pick.model_prob * 100).toFixed(0)}% · {pick.kelly_units.toFixed(1)}u</div>
                  </div>
                  {pick.fair_odd && <AddBtn leg={makePickLeg(pick)} ticket={ticket} />}
                </div>
              );
            })}
          </div>
        )}

        {activeTab === "placares" && (
          <div>
            <div className="text-xs text-slate-500 mb-2">Distribuição Poisson — placares mais prováveis</div>
            <div className="flex gap-3 text-[10px] text-slate-500 mb-2">
              {[["bg-blue-500", "Vitória casa"], ["bg-neutral-500", "Empate"], ["bg-orange-500", "Vitória fora"]].map(([c, l]) => (
                <span key={l} className="flex items-center gap-1">
                  <span className={`w-2 h-2 rounded-full ${c} inline-block`} />{l}
                </span>
              ))}
            </div>
            <ReactECharts option={scoreChartOption} style={{ height: 180 }} theme="dark" />
          </div>
        )}

        {activeTab === "picks" && (
          <div className="space-y-2">
            {analysis.picks.map(pick => (
              <div key={pick.market}
                className="flex items-center gap-3 rounded-lg bg-white/5 border border-white/8 p-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-white truncate">{pick.label}</div>
                  <div className="text-[10px] text-slate-500">{pick.market}</div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="text-right">
                    <div className="text-sm font-black font-mono text-white">{pick.fair_odd?.toFixed(2) ?? "—"}</div>
                    <div className="text-[10px] text-slate-400">{(pick.model_prob * 100).toFixed(0)}%</div>
                  </div>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${confBadge(pick.confidence)}`}>
                    {pick.confidence}
                  </span>
                  {pick.fair_odd && <AddBtn leg={makePickLeg(pick)} ticket={ticket} />}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Live Picks Section ────────────────────────────────────────────────────────

function liveLegId(pick: LivePick) {
  return `live|${pick.event_id}|${pick.market}|${pick.outcome}`;
}

function evBadgeClass(ev: number) {
  if (ev >= 10) return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
  if (ev >= 5)  return "bg-blue-500/20 text-blue-300 border-blue-500/40";
  return "bg-yellow-500/20 text-yellow-300 border-yellow-500/40";
}

function StalenessBadge({ capturedAt }: { capturedAt: string }) {
  const [ageS, setAgeS] = useState(0);
  useEffect(() => {
    const base = Date.now() - new Date(capturedAt).getTime();
    setAgeS(Math.floor(base / 1000));
    const t = setInterval(() => setAgeS(s => s + 1), 1000);
    return () => clearInterval(t);
  }, [capturedAt]);

  const color = ageS < 90
    ? "text-emerald-400"
    : ageS < 180 ? "text-yellow-400" : "text-red-400";
  const label = ageS < 60
    ? `${ageS}s`
    : ageS < 3600 ? `${Math.floor(ageS / 60)}m${ageS % 60}s` : "expirado";

  return (
    <span className={`text-[10px] font-mono ${color}`}>
      ⏱ {label}
    </span>
  );
}

function LivePickCard({ pick, ticket }: { pick: LivePick; ticket: ReturnType<typeof useTicket> }) {
  const leg: TicketLeg = {
    id: liveLegId(pick),
    home: pick.home,
    away: pick.away,
    group: null,
    kickoff: pick.captured_at,
    label: pick.label,
    market: pick.market,
    fairOdd: pick.fair_odd ?? (pick.model_prob > 0 ? parseFloat((1 / pick.model_prob).toFixed(2)) : 0),
    modelProb: pick.model_prob,
    confidence: pick.confidence_label
      ? pick.confidence_label.charAt(0).toUpperCase() + pick.confidence_label.slice(1)
      : "Média",
    type: "live",
    liveMinute: pick.minute,
    liveScore: pick.score,
  };

  return (
    <div className="rounded-xl border border-white/8 bg-black/25 p-3 hover:border-neon-green/20 transition-all">
      {/* Header: times + placar */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <div className="text-[11px] font-bold text-white truncate">
            {pick.home} <span className="text-slate-500">×</span> {pick.away}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="inline-flex items-center gap-1 rounded-full bg-red-500/20 border border-red-500/30 px-1.5 py-0.5 text-[9px] font-bold text-red-400">
              ● {pick.minute}'
            </span>
            <span className="text-[10px] font-mono text-white font-bold">{pick.score}</span>
            <StalenessBadge capturedAt={pick.captured_at} />
          </div>
        </div>
        <AddBtn leg={leg} ticket={ticket} />
      </div>

      {/* Aposta */}
      <div className="text-[11px] text-slate-300 mb-2 leading-tight">{pick.label}</div>

      {/* Stats row */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${evBadgeClass(pick.ev_pct)}`}>
          EV {pick.ev_pct > 0 ? "+" : ""}{pick.ev_pct.toFixed(1)}%
        </span>
        <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-slate-400 border border-white/10">
          odd {pick.market_odd.toFixed(2)}
        </span>
        <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] text-slate-400 border border-white/10">
          {(pick.model_prob * 100).toFixed(0)}% modelo
        </span>
        {pick.suggested_stake_value != null && pick.suggested_stake_value > 0 && (
          <span className="rounded-full bg-blue-900/30 border border-blue-700/30 px-2 py-0.5 text-[10px] text-blue-300">
            R${pick.suggested_stake_value.toFixed(0)} Kelly
          </span>
        )}
      </div>
    </div>
  );
}

function LivePicksSection({ ticket }: { ticket: ReturnType<typeof useTicket> }) {
  const { data, isLoading, isError, dataUpdatedAt, refetch, isFetching } = useLivePicks();
  const picks = data?.picks ?? [];

  // Agrupa por evento
  const byGame = useMemo(() => {
    const map = new Map<number, LivePick[]>();
    for (const p of picks) {
      if (!map.has(p.event_id)) map.set(p.event_id, []);
      map.get(p.event_id)!.push(p);
    }
    return [...map.entries()].sort((a, b) => b[1][0].ev_pct - a[1][0].ev_pct);
  }, [picks]);

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2 w-2 rounded-full ${picks.length > 0 ? "bg-red-500 animate-pulse" : "bg-slate-600"}`} />
          <span className="text-xs text-slate-400">
            {data ? `${data.games_analyzed} jogos analisados · ${picks.length} picks` : "Aguardando jogos ao vivo…"}
          </span>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/5/60 px-2.5 py-1 text-[10px] text-slate-400 hover:text-white transition-all disabled:opacity-40"
        >
          {isFetching ? "⟳ Atualizando…" : "⟳ Atualizar"}
        </button>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-red-900/40 bg-red-950/20 p-6 text-center text-sm text-red-400">
          Erro ao buscar picks ao vivo. Verifique se a API está no ar.
        </div>
      )}

      {!isLoading && !isError && picks.length === 0 && (
        <div className="rounded-xl border border-white/8 bg-black/20 p-8 text-center space-y-2">
          <div className="text-2xl">⚡</div>
          <p className="text-sm font-semibold text-slate-300">Nenhum pick ao vivo disponível</p>
          <p className="text-xs text-slate-500 max-w-xs mx-auto">
            Os picks aparecem automaticamente quando há jogos ao vivo sendo monitorados.
            Abra um jogo na página <strong>Ao Vivo</strong> para popular o cache.
          </p>
        </div>
      )}

      {byGame.map(([eventId, eventPicks]) => {
        const first = eventPicks[0];
        return (
          <div key={eventId} className="space-y-2">
            <div className="flex items-center gap-2 px-1">
              <span className="text-[10px] font-bold text-red-400 uppercase tracking-wider">⚡ Ao Vivo</span>
              <span className="text-xs text-slate-500 font-semibold">{first.home} × {first.away}</span>
              <span className="text-[10px] font-mono text-slate-600">{first.minute}' · {first.score}</span>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {eventPicks.map(p => (
                <LivePickCard key={`${p.event_id}-${p.market}-${p.outcome}`} pick={p} ticket={ticket} />
              ))}
            </div>
          </div>
        );
      })}

      {!isLoading && picks.length > 0 && dataUpdatedAt > 0 && (
        <p className="text-center text-[10px] text-slate-600">
          Atualiza automaticamente a cada 60s · Última atualização: {new Date(dataUpdatedAt).toLocaleTimeString("pt-BR")}
        </p>
      )}
    </div>
  );
}

// ── Summary KPIs ──────────────────────────────────────────────────────────────

function SummaryKpis({
  matches, analyses, ticketCount,
}: {
  matches: TodayMatch[]; analyses: AnalysisResponse[]; ticketCount: number;
}) {
  const upcoming = matches.filter(m => !m.played);
  const played = matches.filter(m => m.played);
  const allSingles = analyses.flatMap(a => a.ticket.singles);
  const highConf = allSingles.filter(p => p.confidence === "Alta").length;
  const combos = analyses.filter(a => a.ticket.combo).length;

  const kpis = [
    { label: "Jogos hoje", val: upcoming.length, sub: played.length > 0 ? `${played.length} encerrado` : "a jogar", color: "text-white" },
    { label: "Alta Conf.", val: highConf, sub: `de ${allSingles.length} picks`, color: "text-emerald-300" },
    { label: "Combos", val: combos, sub: "sugeridos", color: "text-blue-300" },
    { label: "Bilhete", val: ticketCount, sub: ticketCount > 0 ? "pernas montadas" : "vazio", color: "text-amber-300" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {kpis.map(k => (
        <div key={k.label} className="rounded-xl border border-white/8 bg-black/25 p-4 text-center">
          <div className={`text-2xl font-black font-mono ${k.color}`}>{k.val}</div>
          <div className="text-xs font-semibold text-slate-300 mt-0.5">{k.label}</div>
          <div className="text-[10px] text-slate-600 mt-0.5">{k.sub}</div>
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type Section = "bilhetes" | "aovivo" | "jogos" | "simulador" | "grafico";

export function CopaCentralPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<Section>("bilhetes");
  const ticket = useTicket();

  // Auto-switch to simulator tab if user just added first pick
  const prevCount = useState(ticket.legs.length);
  useEffect(() => {
    if (ticket.legs.length === 1 && prevCount[0] === 0) {
      setActiveSection("simulador");
    }
    prevCount[1](ticket.legs.length);
  }, [ticket.legs.length]);

  const { data: todayData, isLoading: loadingToday } = useQuery<TodayResponse>({
    queryKey: ["pregame-today-central", "v2", "today_only"],
    queryFn: () => apiFetch("/worldcup/pregame/today?today_only=true&tz=America/Sao_Paulo"),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
  });

  const matches = todayData?.matches ?? [];
  const upcoming = matches.filter(m => !m.played);

  const analysisQueries = useQueries({
    queries: upcoming.map(m => ({
      queryKey: ["pregame-analysis-central", m.home_team, m.away_team, m.phase],
      queryFn: () =>
        apiFetch<AnalysisResponse>(
          `/worldcup/pregame/analysis?home=${encodeURIComponent(m.home_team)}&away=${encodeURIComponent(m.away_team)}&phase=${m.phase}`
        ),
      staleTime: 10 * 60 * 1000,
    })),
  });

  const analyses = analysisQueries
    .map((q, i) => q.data ? { ...q.data, kickoff: upcoming[i]?.kickoff_utc ?? "" } : null)
    .filter((a): a is AnalysisResponse & { kickoff: string } => a !== null);

  const analysisMap = useMemo(() => {
    const map: Record<string, AnalysisResponse> = {};
    for (const a of analyses) map[`${a.home_team}|${a.away_team}`] = a;
    return map;
  }, [analyses]);

  const selectedMatch = matches.find(m => m.id === selectedId);
  const selectedAnalysis = selectedMatch
    ? analysisMap[`${selectedMatch.home_team}|${selectedMatch.away_team}`]
    : undefined;

  const isLoadingAnalyses = analysisQueries.some(q => q.isLoading);

  const { data: liveData } = useLivePicks();
  const livePicks = liveData?.picks ?? [];

  const sections: { key: Section; label: string; badge?: string }[] = [
    { key: "bilhetes", label: "🎯 Melhores Bilhetes", badge: analyses.length > 0 ? String(analyses.length) : undefined },
    { key: "aovivo", label: "⚡ Ao Vivo", badge: livePicks.length > 0 ? String(livePicks.length) : undefined },
    { key: "jogos", label: "⚽ Jogos" },
    { key: "simulador", label: "🎟️ Meu Bilhete", badge: ticket.legs.length > 0 ? String(ticket.legs.length) : undefined },
    { key: "grafico", label: "📊 Gráficos" },
  ];

  return (
    <PageTransition>
      <PageHeader
        title="Copa 2026 — Central de Apostas"
        subtitle="Modelo Poisson + Kelly · Simulador de bilhete · Gemini Research"
        badge={ticket.legs.length > 0 ? `${ticket.legs.length} no bilhete` : undefined}
        badgeColor="green"
      />

      {/* KPIs */}
      {loadingToday ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
      ) : (
        <SummaryKpis matches={matches} analyses={analyses} ticketCount={ticket.legs.length} />
      )}

      <LiveDashboardTabs
        tabs={sections.map((s) => ({ id: s.key, label: s.label, count: s.badge ? Number(s.badge) : undefined }))}
        activeId={activeSection}
        onChange={(id) => setActiveSection(id as Section)}
      />

      {/* ── Melhores Bilhetes ── */}
      {activeSection === "bilhetes" && (
        <div>
          {isLoadingAnalyses && analyses.length === 0 ? (
            <div className="space-y-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-36 rounded-xl" />)}</div>
          ) : upcoming.length === 0 ? (
            <div className="rounded-xl border border-white/8 bg-black/20 p-8 text-center text-slate-500 text-sm">
              Nenhum jogo pendente hoje.
            </div>
          ) : (
            <BestTicketsSection analyses={analyses} ticket={ticket} />
          )}
          {isLoadingAnalyses && analyses.length > 0 && (
            <p className="text-center text-xs text-slate-600 mt-3 animate-pulse">Carregando análises restantes…</p>
          )}
        </div>
      )}

      {/* ── Ao Vivo ── */}
      {activeSection === "aovivo" && (
        <LivePicksSection ticket={ticket} />
      )}

      {/* ── Jogos do Dia ── */}
      {activeSection === "jogos" && (
        <div className="space-y-4">
          {loadingToday ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-48 rounded-2xl" />)}
            </div>
          ) : matches.length === 0 ? (
            <div className="rounded-xl border border-white/8 p-8 text-center text-slate-500 text-sm space-y-2">
              <p>Nenhum jogo da Copa hoje.</p>
              {todayData?.next_match ? (
                <p className="text-slate-300">
                  Próximo:{" "}
                  <span className="font-semibold text-white">
                    {todayData.next_match.home_team} × {todayData.next_match.away_team}
                  </span>
                  {todayData.next_match.kickoff_br
                    ? ` · ${todayData.next_match.kickoff_br}`
                    : ""}
                  {todayData.next_match.eta_label
                    ? ` (${todayData.next_match.eta_label})`
                    : ""}
                </p>
              ) : (
                <p className="text-xs text-slate-600">
                  Sem próximo confronto no calendário ainda.
                </p>
              )}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {matches.map(m => (
                  <GameCard key={m.id} match={m}
                    analysis={analysisMap[`${m.home_team}|${m.away_team}`]}
                    isSelected={selectedId === m.id}
                    onClick={() => setSelectedId(selectedId === m.id ? null : m.id)}
                  />
                ))}
              </div>
              {selectedMatch && selectedAnalysis && (
                <ExpandedAnalysis match={selectedMatch} analysis={selectedAnalysis} ticket={ticket} />
              )}
              {selectedMatch && !selectedAnalysis && (
                <div className="rounded-xl border border-white/8 bg-black/20 p-6 text-center">
                  {selectedMatch.played
                    ? <p className="text-slate-500 text-sm">Jogo encerrado.</p>
                    : <div className="flex items-center justify-center gap-2 text-slate-400 text-sm">
                        <div className="animate-spin">⚙️</div> Carregando análise…
                      </div>
                  }
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Simulador de Bilhete ── */}
      {activeSection === "simulador" && (
        <CentralTicketSimulator ticket={ticket} analyses={analyses} />
      )}

      {/* ── Gráficos ── */}
      {activeSection === "grafico" && (
        <div className="space-y-4">
          <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
            <div className="text-sm font-bold text-white mb-1">Distribuição de Probabilidades</div>
            <div className="text-xs text-slate-500 mb-4">Modelo Poisson calibrado · Copa 2026</div>
            {loadingToday ? <Skeleton className="h-48 w-full" /> : <GamesOverviewChart matches={matches} />}
          </div>
          {upcoming.length > 0 && (
            <div>
              <div className="text-sm font-bold text-white mb-3">Confiança do Modelo por Jogo</div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {upcoming.map(m => (
                  <div key={m.id} className="rounded-xl border border-white/8 bg-black/20 p-3">
                    <div className="text-[10px] text-slate-500 truncate">{m.home_team}</div>
                    <div className="text-[10px] text-slate-500 truncate mb-0.5">× {m.away_team}</div>
                    <ConfidenceGauge value={m.confidence} label={m.prediction.split(" ").slice(0, 2).join(" ")} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeSection !== "simulador" && (
        <FloatingTicketBadge count={ticket.legs.length} onClick={() => setActiveSection("simulador")} />
      )}
    </PageTransition>
  );
}
