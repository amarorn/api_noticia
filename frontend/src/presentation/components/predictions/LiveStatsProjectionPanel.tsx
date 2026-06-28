/**
 * LiveStatsProjectionPanel — Stats ao vivo + projeções até o fim
 *
 * Layout: uma linha por mercado com  [Ícone · Mercado] [Home X Away] [→ Proj FT] [Apostar]
 * Só aparece se tiver dado real (nunca mostra linha vazia).
 */
import type { SuperbetLiveAdvice, RefereeMarketLine } from "@/domain/entities";

interface Props {
  data: SuperbetLiveAdvice;
}

// ── Cores ─────────────────────────────────────────────────────────────────────
const H  = "#38bdf8"; // home / sky
const A  = "#fb923c"; // away / orange
const G  = "#4ade80"; // verde = over/apostar
const BL = "#60a5fa"; // azul  = under

// ── Pill "Apostar" ─────────────────────────────────────────────────────────────
function BetPill({
  label, prob, rec, conf,
}: {
  label: string;
  prob: number;
  rec: "over" | "under" | "neutro";
  conf?: "alta" | "media" | "baixa";
}) {
  if (rec === "neutro") return null;
  const color = rec === "over" ? G : BL;
  const border = conf === "alta" ? `${color}60` : `${color}30`;
  const bg     = conf === "alta" ? `${color}18` : `${color}0c`;
  return (
    <div
      className="inline-flex items-center gap-1 rounded-lg border px-2 py-0.5"
      style={{ borderColor: border, background: bg }}
    >
      <span className="text-[10px] font-bold" style={{ color }}>
        {label}
      </span>
      <span className="font-mono text-[11px] font-semibold" style={{ color }}>
        {Math.round(prob * 100)}%
      </span>
      {conf === "alta" && <span className="text-[9px]" style={{ color }}>★</span>}
    </div>
  );
}

// ── Linha de mercado ───────────────────────────────────────────────────────────
// Layout:  [Ícone · Label]  [Atual home × away (total)]  [→ Prev. FT]  [Pill]
function MarketRow({
  icon, label,
  homeVal, awayVal,
  totalNow,
  projHome, projAway, projTotal,
  bet,
}: {
  icon: string;
  label: string;
  homeVal?: number | null;
  awayVal?: number | null;
  totalNow?: number | null;
  projHome?: number | null;
  projAway?: number | null;
  projTotal?: number | null;
  bet?: React.ReactNode;
}) {
  const hasNow  = homeVal != null || awayVal != null;
  const hasProj = projTotal != null || projHome != null;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-white/5 py-2.5 last:border-0">
      {/* Ícone + label */}
      <div className="flex w-28 shrink-0 items-center gap-1.5">
        <span className="text-sm leading-none">{icon}</span>
        <span className="text-[11px] font-semibold text-slate-400">{label}</span>
      </div>

      {/* Atual */}
      <div className="flex items-baseline gap-1">
        <span className="text-[9px] text-slate-600">Atual</span>
        {hasNow ? (
          <span className="font-mono text-sm font-bold">
            <span style={{ color: H }}>{homeVal ?? "–"}</span>
            <span className="mx-0.5 text-slate-600">×</span>
            <span style={{ color: A }}>{awayVal ?? "–"}</span>
          </span>
        ) : (
          <span className="font-mono text-sm font-bold text-slate-500">—</span>
        )}
        {totalNow != null && (
          <span className="ml-0.5 text-[10px] text-slate-500">({totalNow})</span>
        )}
      </div>

      {/* Seta + Projeção FT */}
      {hasProj && (
        <div className="flex items-baseline gap-1">
          <span className="text-slate-600">→</span>
          <span className="text-[9px] text-slate-600">Prev. FT</span>
          {projHome != null && projAway != null ? (
            <span className="font-mono text-sm font-bold">
              <span style={{ color: H }}>{projHome.toFixed(1)}</span>
              <span className="mx-0.5 text-slate-600">×</span>
              <span style={{ color: A }}>{projAway.toFixed(1)}</span>
            </span>
          ) : null}
          {projTotal != null && (
            <span className="rounded-md bg-white/8 px-1.5 py-0.5 font-mono text-[11px] font-bold text-white">
              ~{projTotal.toFixed(1)}
            </span>
          )}
        </div>
      )}

      {/* Pill de aposta */}
      {bet && <div className="ml-auto">{bet}</div>}
    </div>
  );
}

// ── Barra visual Over/Under ────────────────────────────────────────────────────
function ProbBar({
  overProb, overLabel, underLabel,
}: {
  overProb: number; overLabel: string; underLabel: string;
}) {
  const op = Math.round(overProb * 100);
  const up = 100 - op;
  return (
    <div className="space-y-1.5">
      <div className="flex h-6 overflow-hidden rounded-xl">
        <div
          className="flex items-center justify-center transition-all duration-500"
          style={{ width: `${op}%`, background: `${G}28`, minWidth: op > 5 ? 40 : 0 }}
        >
          {op >= 12 && <span className="font-mono text-[11px] font-bold" style={{ color: G }}>{op}%</span>}
        </div>
        <div
          className="flex items-center justify-center"
          style={{ width: `${up}%`, background: `${BL}1c`, minWidth: up > 5 ? 40 : 0 }}
        >
          {up >= 12 && <span className="font-mono text-[11px] font-bold" style={{ color: BL }}>{up}%</span>}
        </div>
      </div>
      <div className="flex justify-between px-1 text-[9px]">
        <span style={{ color: `${G}cc` }}>{overLabel}</span>
        <span style={{ color: `${BL}cc` }}>{underLabel}</span>
      </div>
    </div>
  );
}

// ── Melhor linha de um array ───────────────────────────────────────────────────
function bestLine(lines: RefereeMarketLine[]): RefereeMarketLine | null {
  const recs = lines.filter((l) => l.recommendation !== "neutro");
  if (!recs.length) return null;
  return recs.sort((a, b) =>
    (b.confidence === "alta" ? 2 : b.confidence === "media" ? 1 : 0) -
    (a.confidence === "alta" ? 2 : a.confidence === "media" ? 1 : 0)
  )[0];
}

// ── Componente principal ───────────────────────────────────────────────────────
export function LiveStatsProjectionPanel({ data }: Props) {
  const s       = data.inplaySummary;
  const stats   = data.liveStats;
  const cp      = data.cornersProjection ?? null;
  const refMkts = s.refereeMarkets ?? null;
  const minute  = data.minute ?? 0;

  const [homeScore, awayScore] = (data.currentScore ?? "0x0").split("x").map(Number);
  const currentGoals = (homeScore ?? 0) + (awayScore ?? 0);

  // λ para projeção de gols
  const λH = s.lambdaAdjustment?.lambdaFullHome ?? null;
  const λA = s.lambdaAdjustment?.lambdaFullAway ?? null;
  const projGoals = λH != null && λA != null && minute < 90
    ? currentGoals + (λH + λA) * ((90 - minute) / 90)
    : null;
  const over25 = s.over25 ?? null;

  // Escanteios
  const hC = stats?.homeCorners ?? null;
  const aC = stats?.awayCorners ?? null;
  const cornersLineRec = cp?.lineProbs
    ? (() => {
        const entries = Object.entries(cp.lineProbs).map(([line, prob]) => ({
          line: Number(line), overProb: prob, underProb: 1 - prob,
          overOddsFair: prob > 0 ? 1 / prob : 99,
          underOddsFair: prob < 1 ? 1 / (1 - prob) : 99,
          expectedTotal: cp.expectedFtTotal,
          recommendation: (prob > 0.58 ? "over" : prob < 0.42 ? "under" : "neutro") as "over" | "under" | "neutro",
          confidence: (Math.abs(prob - 0.5) > 0.15 ? "alta" : "media") as "alta" | "media" | "baixa",
          edge: null,
        }));
        return bestLine(entries);
      })()
    : null;

  // Cartões
  const hY = stats?.homeYellowCards ?? null;
  const aY = stats?.awayYellowCards ?? null;
  const refYellow = refMkts?.yellowCards ?? null;
  const yellowRec = refYellow ? bestLine(refYellow.overLines) : null;

  // Faltas
  const refFouls  = refMkts?.fouls ?? null;
  const foulsRec  = refFouls ? bestLine(refFouls.overLines) : null;

  // Especiais
  const refRed     = refMkts?.redCards ?? null;
  const refPenalty = refMkts?.penalties ?? null;

  // Verifica se há algo para mostrar
  const hasGoals   = over25 != null || projGoals != null;
  const hasCorners = hC != null || cp != null;
  const hasCards   = hY != null || refYellow != null;
  const hasFouls   = refFouls != null;
  const hasSpecial = refRed != null || refPenalty != null;

  if (!hasGoals && !hasCorners && !hasCards && !hasFouls && !hasSpecial) return null;

  return (
    <section className="overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900/80 via-slate-900/50 to-slate-950/90 px-4 py-3 backdrop-blur-sm">

      {/* Título */}
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600">
          Stats &amp; Projeções até o fim
        </span>
        <span className="h-px flex-1 bg-white/5" />
        <span className="font-mono text-[10px] text-slate-600">{minute}&apos;</span>
      </div>

      {/* ── Gols ── */}
      {hasGoals && (
        <div className="space-y-2">
          <MarketRow
            icon="⚽" label="Gols"
            homeVal={homeScore} awayVal={awayScore}
            totalNow={currentGoals}
            projTotal={projGoals}
            bet={
              over25 != null ? (
                <BetPill
                  label="Over 2.5"
                  prob={over25}
                  rec={over25 > 0.55 ? "over" : over25 < 0.45 ? "under" : "neutro"}
                  conf={Math.abs(over25 - 0.5) > 0.2 ? "alta" : "media"}
                />
              ) : null
            }
          />
          {over25 != null && (
            <ProbBar overProb={over25} overLabel="Over 2.5" underLabel="Under 2.5" />
          )}
        </div>
      )}

      {/* ── Escanteios ── */}
      {hasCorners && (
        <MarketRow
          icon="🚩" label="Escanteios"
          homeVal={hC} awayVal={aC}
          totalNow={hC != null && aC != null ? hC + aC : null}
          projHome={cp?.expectedFtHome ?? null}
          projAway={cp?.expectedFtAway ?? null}
          projTotal={cp?.expectedFtTotal ?? null}
          bet={
            cornersLineRec ? (
              <BetPill
                label={`${cornersLineRec.recommendation === "over" ? "Over" : "Under"} ${cornersLineRec.line}`}
                prob={cornersLineRec.recommendation === "over" ? cornersLineRec.overProb : cornersLineRec.underProb}
                rec={cornersLineRec.recommendation}
                conf={cornersLineRec.confidence}
              />
            ) : null
          }
        />
      )}

      {/* ── Cartões amarelos ── */}
      {hasCards && (
        <MarketRow
          icon="🟨" label="Amarelos"
          homeVal={hY} awayVal={aY}
          totalNow={hY != null && aY != null ? hY + aY : null}
          projTotal={refYellow?.expectedTotal ?? null}
          bet={
            yellowRec ? (
              <BetPill
                label={`${yellowRec.recommendation === "over" ? "Over" : "Under"} ${yellowRec.line}`}
                prob={yellowRec.recommendation === "over" ? yellowRec.overProb : yellowRec.underProb}
                rec={yellowRec.recommendation}
                conf={yellowRec.confidence}
              />
            ) : null
          }
        />
      )}

      {/* ── Faltas ── */}
      {hasFouls && (
        <MarketRow
          icon="🤚" label="Faltas"
          projTotal={refFouls!.expectedTotal}
          bet={
            foulsRec ? (
              <BetPill
                label={`${foulsRec.recommendation === "over" ? "Over" : "Under"} ${foulsRec.line}`}
                prob={foulsRec.recommendation === "over" ? foulsRec.overProb : foulsRec.underProb}
                rec={foulsRec.recommendation}
                conf={foulsRec.confidence}
              />
            ) : null
          }
        />
      )}

      {/* ── Vermelho + Pênalti (inline) ── */}
      {hasSpecial && (
        <div className="mt-1 flex flex-wrap gap-2 border-t border-white/5 pt-2.5">
          {refRed != null && (
            <div className="flex items-center gap-2 rounded-xl border border-white/7 bg-white/[0.03] px-3 py-1.5">
              <span className="text-sm">🟥</span>
              <div>
                <p className="text-[10px] text-slate-500">Cartão vermelho</p>
                <p className="font-mono text-sm font-bold" style={{ color: refRed.yesProb > 0.25 ? "#fbbf24" : "#64748b" }}>
                  {Math.round(refRed.yesProb * 100)}%
                  <span className="ml-1 text-[10px] font-normal text-slate-600">
                    · odd {refRed.yesOddsFair.toFixed(2)}
                  </span>
                </p>
              </div>
            </div>
          )}
          {refPenalty != null && (
            <div className="flex items-center gap-2 rounded-xl border border-white/7 bg-white/[0.03] px-3 py-1.5">
              <span className="text-sm">🏳️</span>
              <div>
                <p className="text-[10px] text-slate-500">Pênalti</p>
                <p className="font-mono text-sm font-bold" style={{ color: refPenalty.yesProb > 0.2 ? "#fbbf24" : "#64748b" }}>
                  {Math.round(refPenalty.yesProb * 100)}%
                  <span className="ml-1 text-[10px] font-normal text-slate-600">
                    · odd {refPenalty.yesOddsFair.toFixed(2)}
                  </span>
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Rodapé: aviso se dados de árbitro ausentes */}
      {!refYellow && !refFouls && (
        <p className="mt-2 text-[9px] text-slate-700">
          Projeção de cartões/faltas requer .txt do árbitro via Análise pré-jogo
        </p>
      )}
    </section>
  );
}
