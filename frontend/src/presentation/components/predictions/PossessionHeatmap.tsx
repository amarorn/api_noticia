/**
 * Mapa de posse de bola derivado dos modelos KXL + Poisson.
 *
 * Fontes de dados reais usadas:
 *  - kxlBaseline.homeSnapshot / awaySnapshot: indices KXL calculados a partir
 *    do team_baselines.json (possession_pct, attack_index, defense_index,
 *    control_index, counter_attack, gk_inside_weakness_pct)
 *  - kxlCollision setores: colisao, attackDna, permissividade (KXL Fase 3)
 *  - poissonFactors: lambdaHome / lambdaAway (Dixon-Coles calibrado)
 *
 * Grade: 3 corredores (esq / meio / dir) × 4 faixas de profundidade = 12 zonas.
 */

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type {
  GoalModelFactors,
  KxlCollisionSide,
  KxlTeamSnapshot,
  WcPrediction,
} from "@/domain/entities";
import { outcomeColors } from "@/presentation/theme";

// ─── Tipos internos ────────────────────────────────────────────────────────────

/** [depth_idx][corridor_idx]  depth 0=caixa_ataque ... 3=caixa_defesa */
type ZoneMatrix = number[][];

type HeatMode = "home" | "away" | "duelo";

interface ZoneInfo {
  col: number;
  depth: number;
  homeVal: number;
  awayVal: number;
}

// ─── Constantes de layout ──────────────────────────────────────────────────────

const CORRIDORS = ["esquerda", "meio", "direita"] as const;
const CORR_LABELS = ["Esq.", "Centro", "Dir."] as const;
const DEPTH_LABELS = ["Caixa ataque", "Terço ofensivo", "Meio-campo", "Terço defensivo"] as const;

// Centro naturalmente mais denso em posse
const CORR_BIAS = [0.91, 1.18, 0.91] as const;

// ─── Cálculo de zonas a partir de dados reais ─────────────────────────────────

function computeZones(
  collision: KxlCollisionSide | null,
  snap: KxlTeamSnapshot | null,
  lambda: number,
): ZoneMatrix {
  // Todos os valores vêm do WcBaselineSnapshot calculado pelo backend
  const poss = snap != null ? snap.possessionPct / 100 : 0.5;
  const ctrl = snap?.controlIndex ?? 0.70;
  const atk = snap?.attackIndex ?? 0.65;
  const def = snap?.defenseIndex ?? 0.65;
  // counterAttack é gols de contra-ataque por jogo (0-3 range)
  const counter = Math.min(1, (snap?.counterAttack ?? 1.0) / 3.0);
  // gkInsideWeaknessPct é 0-100; 70 = padrão neutro
  const gkWk = snap != null ? snap.gkInsideWeaknessPct / 100 : 0.70;

  const sectorMap = new Map(
    (collision?.setores ?? []).map((s) => [s.setor.toLowerCase(), s]),
  );

  return [
    // depth 0 — caixa de ataque: DNA setorial + lambda Dixon-Coles
    CORRIDORS.map((c, i) => {
      const s = sectorMap.get(c);
      const col = s?.colisao ?? 0.22;
      const dna = s?.attackDna ?? 0.22;
      return Math.min(1, col * (lambda / 1.5) * atk * 3.0 * CORR_BIAS[i] + dna * 0.25);
    }),
    // depth 1 — terço ofensivo: posse real × ataque × contra-ataque
    CORRIDORS.map((_, i) =>
      Math.min(1, poss * atk * (1 + counter * 0.18) * CORR_BIAS[i] * 1.35),
    ),
    // depth 2 — meio-campo: posse real × controle
    CORRIDORS.map((_, i) =>
      Math.min(1, poss * ctrl * CORR_BIAS[i] * 1.1),
    ),
    // depth 3 — terço defensivo: defesa × permissividade setorial real
    CORRIDORS.map((c, i) => {
      const s = sectorMap.get(c);
      const oppPerm = s?.permissividade ?? 0.30;
      return Math.min(1, def * (1 - oppPerm * 0.4) * (1 - gkWk * 0.2) * CORR_BIAS[i]);
    }),
  ];
}

/**
 * Calcula posse global a partir dos dados reais do KXL snapshot.
 * Usa possession_pct direto quando disponível (é o dado mais preciso).
 */
function computeOverallPossession(
  homeSnap: KxlTeamSnapshot | null,
  awaySnap: KxlTeamSnapshot | null,
  homeCollision: KxlCollisionSide | null,
  awayCollision: KxlCollisionSide | null,
): { pct: number; source: string } {
  // Prioridade máxima: possession_pct do baseline (dado direto da seleção)
  if (homeSnap != null && awaySnap != null) {
    const hp = homeSnap.possessionPct;
    const ap = awaySnap.possessionPct;
    if (hp + ap > 0) {
      return { pct: hp / (hp + ap), source: "KXL baseline · ECPB_posse_media" };
    }
  }

  // Fallback: controle × energia KXL (índices calculados)
  const hc = homeSnap?.controlIndex ?? 0.70;
  const ac = awaySnap?.controlIndex ?? 0.70;
  const he = homeCollision?.energia ?? 0.80;
  const ae = awayCollision?.energia ?? 0.80;
  const hScore = hc * 0.55 + he * 0.45;
  const aScore = ac * 0.55 + ae * 0.45;
  const total = hScore + aScore;
  return {
    pct: total > 0 ? hScore / total : 0.5,
    source: "Derivado de controle KXL + energia setorial",
  };
}

// ─── Cores ─────────────────────────────────────────────────────────────────────

function zoneColor(intensity: number, mode: HeatMode, homeVal: number, awayVal: number): string {
  const alpha = 0.08 + intensity * 0.62;

  if (mode === "home") return `rgba(0, 255, 136, ${alpha})`;
  if (mode === "away") return `rgba(168, 85, 247, ${alpha})`;

  const net = homeVal - awayVal;
  if (net > 0.04) return `rgba(0, 255, 136, ${0.08 + Math.abs(net) * 0.65})`;
  if (net < -0.04) return `rgba(168, 85, 247, ${0.08 + Math.abs(net) * 0.65})`;
  return `rgba(0, 212, 255, ${0.10 + intensity * 0.25})`;
}

// ─── Componente principal ──────────────────────────────────────────────────────

export interface PossessionHeatmapProps {
  prediction: WcPrediction;
  className?: string;
}

export function PossessionHeatmap({ prediction, className = "" }: PossessionHeatmapProps) {
  const [mode, setMode] = useState<HeatMode>("duelo");
  const [activeZone, setActiveZone] = useState<ZoneInfo | null>(null);

  const baseline = prediction.modelBreakdown.kxlBaseline;
  const collision = prediction.modelBreakdown.kxlCollision;
  const factors = prediction.modelBreakdown.poissonFactors;

  const homeSnap = baseline?.homeSnapshot ?? null;
  const awaySnap = baseline?.awaySnapshot ?? null;

  const lambdaH = factors?.lambdaHome ?? 1.2;
  const lambdaA = factors?.lambdaAway ?? 1.0;

  const homeZones = useMemo(
    () => computeZones(collision?.home ?? null, homeSnap, lambdaH),
    [collision, homeSnap, lambdaH],
  );
  const awayZones = useMemo(
    () => computeZones(collision?.away ?? null, awaySnap, lambdaA),
    [collision, awaySnap, lambdaA],
  );

  const { pct: possessionHome, source: possSource } = useMemo(
    () => computeOverallPossession(homeSnap, awaySnap, collision?.home ?? null, collision?.away ?? null),
    [homeSnap, awaySnap, collision],
  );

  const allVals = homeZones.flat().concat(awayZones.flat());
  const maxVal = Math.max(...allVals, 0.01);

  const PITCH_W = 100;
  const PITCH_H = 160;
  const ZONE_W = PITCH_W / 3;
  const ZONE_H = PITCH_H / 4;

  return (
    <div className={`space-y-4 ${className}`}>
      <PossessionBar
        homeTeam={prediction.homeTeam}
        awayTeam={prediction.awayTeam}
        homePct={possessionHome}
        source={possSource}
      />

      <div className="flex flex-wrap gap-2">
        <ModeBtn active={mode === "duelo"} onClick={() => setMode("duelo")} label="Duelo" />
        <ModeBtn
          active={mode === "home"}
          onClick={() => setMode("home")}
          label={prediction.homeTeam}
          color={outcomeColors["1"]}
        />
        <ModeBtn
          active={mode === "away"}
          onClick={() => setMode("away")}
          label={prediction.awayTeam}
          color={outcomeColors["2"]}
        />
      </div>

      <div className="relative mx-auto max-w-xs sm:max-w-sm">
        <svg
          viewBox={`0 0 ${PITCH_W} ${PITCH_H}`}
          className="w-full select-none rounded-lg"
          role="img"
          aria-label="Mapa de posse de bola por zona do gramado"
        >
          <defs>
            <linearGradient id="poss-grass" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#173622" />
              <stop offset="50%" stopColor="#1c4228" />
              <stop offset="100%" stopColor="#173622" />
            </linearGradient>
          </defs>

          <rect x="0" y="0" width={PITCH_W} height={PITCH_H} fill="url(#poss-grass)" />

          {[0, 1, 2, 3].map((depth) =>
            [0, 1, 2].map((col) => {
              const homeVal = homeZones[depth]?.[col] ?? 0;
              const awayVal = awayZones[depth]?.[col] ?? 0;
              const rawVal = mode === "away" ? awayVal : homeVal;

              const duelIntensity =
                mode === "duelo"
                  ? Math.abs(homeVal - awayVal) / maxVal
                  : rawVal / maxVal;

              const fill = zoneColor(duelIntensity, mode, homeVal, awayVal);
              const x = col * ZONE_W;
              const y = depth * ZONE_H;
              const isActive = activeZone?.col === col && activeZone?.depth === depth;

              return (
                <motion.rect
                  key={`z-${depth}-${col}`}
                  x={x + 0.5}
                  y={y + 0.5}
                  width={ZONE_W - 1}
                  height={ZONE_H - 1}
                  fill={fill}
                  stroke={isActive ? "rgba(255,255,255,0.7)" : "none"}
                  strokeWidth={0.6}
                  className="cursor-pointer"
                  animate={{ opacity: isActive ? 1 : 0.88 }}
                  onMouseEnter={() => setActiveZone({ col, depth, homeVal, awayVal })}
                  onMouseLeave={() => setActiveZone(null)}
                  onClick={() =>
                    setActiveZone((prev) =>
                      prev?.col === col && prev?.depth === depth
                        ? null
                        : { col, depth, homeVal, awayVal },
                    )
                  }
                />
              );
            }),
          )}

          {/* Linhas do campo */}
          <rect x="1" y="1" width={PITCH_W - 2} height={PITCH_H - 2}
            fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="0.6" />
          <line x1="1" y1={PITCH_H / 2} x2={PITCH_W - 1} y2={PITCH_H / 2}
            stroke="rgba(255,255,255,0.22)" strokeWidth="0.5" />
          <circle cx={PITCH_W / 2} cy={PITCH_H / 2} r="10"
            fill="none" stroke="rgba(255,255,255,0.18)" strokeWidth="0.4" />
          <circle cx={PITCH_W / 2} cy={PITCH_H / 2} r="0.9"
            fill="rgba(255,255,255,0.25)" />
          <rect x="28" y="1" width="44" height="20"
            fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.4" />
          <rect x="38" y="1" width="24" height="8"
            fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="0.35" />
          <circle cx={PITCH_W / 2} cy="13" r="0.8" fill="rgba(255,255,255,0.25)" />
          <rect x="28" y={PITCH_H - 21} width="44" height="20"
            fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.4" />
          <rect x="38" y={PITCH_H - 9} width="24" height="8"
            fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="0.35" />
          <circle cx={PITCH_W / 2} cy={PITCH_H - 13} r="0.8" fill="rgba(255,255,255,0.25)" />
          <rect x="40" y="0" width="20" height="3"
            fill="rgba(255,255,255,0.1)" stroke="rgba(255,255,255,0.25)" strokeWidth="0.4" />
          <rect x="40" y={PITCH_H - 3} width="20" height="3"
            fill="rgba(255,255,255,0.1)" stroke="rgba(255,255,255,0.25)" strokeWidth="0.4" />
          {[ZONE_W, ZONE_W * 2].map((x) => (
            <line key={x} x1={x} y1="1" x2={x} y2={PITCH_H - 1}
              stroke="rgba(255,255,255,0.07)" strokeWidth="0.3" strokeDasharray="2,3" />
          ))}

          {DEPTH_LABELS.map((label, i) => (
            <text key={i} x={PITCH_W - 1.5} y={i * ZONE_H + ZONE_H / 2}
              textAnchor="end" dominantBaseline="middle"
              fill="rgba(255,255,255,0.2)" fontSize="3.2" fontWeight="500" pointerEvents="none">
              {label}
            </text>
          ))}

          <text x={PITCH_W / 2} y="5.5" textAnchor="middle"
            fill="rgba(255,255,255,0.55)" fontSize="3.8" fontWeight="700" pointerEvents="none">
            {(mode === "away" ? prediction.awayTeam : prediction.homeTeam).slice(0, 14).toUpperCase()}
          </text>
          <text x={PITCH_W / 2} y={PITCH_H - 2.5} textAnchor="middle"
            fill="rgba(255,255,255,0.25)" fontSize="3.2" fontWeight="500" pointerEvents="none">
            {(mode === "away" ? prediction.homeTeam : prediction.awayTeam).slice(0, 14)}
          </text>
        </svg>

        <AnimatePresence>
          {activeZone && (
            <motion.div
              key="tooltip"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              className="absolute bottom-2 left-2 right-2 rounded-xl border border-white/15 bg-surface/95 p-3 shadow-xl backdrop-blur-md"
            >
              <ZoneTooltip
                zone={activeZone}
                homeTeam={prediction.homeTeam}
                awayTeam={prediction.awayTeam}
                mode={mode}
                factors={factors}
                homeSnap={homeSnap}
                awaySnap={awaySnap}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-4 text-[11px] text-slate-500">
        <LegendItem color="rgba(0,255,136,0.6)" label={prediction.homeTeam} />
        <LegendItem color="rgba(0,212,255,0.4)" label="Neutro" />
        <LegendItem color="rgba(168,85,247,0.6)" label={prediction.awayTeam} />
      </div>

      <DataSourcesNote
        prediction={prediction}
        homeSnap={homeSnap}
        possSource={possSource}
      />
    </div>
  );
}

// ─── Sub-componentes ───────────────────────────────────────────────────────────

function PossessionBar({
  homeTeam,
  awayTeam,
  homePct,
  source,
}: {
  homeTeam: string;
  awayTeam: string;
  homePct: number;
  source: string;
}) {
  const awayPct = 1 - homePct;
  const homePctInt = Math.round(homePct * 100);
  const awayPctInt = 100 - homePctInt;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-xs">
        <span className="font-semibold" style={{ color: outcomeColors["1"] }}>
          {homeTeam}
        </span>
        <span className="text-[10px] text-slate-600">{source}</span>
        <span className="font-semibold" style={{ color: outcomeColors["2"] }}>
          {awayTeam}
        </span>
      </div>
      <div className="flex h-7 overflow-hidden rounded-xl border border-white/[0.06]">
        <div
          className="flex items-center justify-center text-xs font-bold transition-all duration-700"
          style={{
            width: `${homePct * 100}%`,
            background: `linear-gradient(90deg, ${outcomeColors["1"]}30, ${outcomeColors["1"]}55)`,
            color: outcomeColors["1"],
          }}
        >
          {homePctInt}%
        </div>
        <div
          className="flex items-center justify-center text-xs font-bold transition-all duration-700"
          style={{
            width: `${awayPct * 100}%`,
            background: `linear-gradient(90deg, ${outcomeColors["2"]}55, ${outcomeColors["2"]}30)`,
            color: outcomeColors["2"],
          }}
        >
          {awayPctInt}%
        </div>
      </div>
    </div>
  );
}

function ZoneTooltip({
  zone,
  homeTeam,
  awayTeam,
  mode,
  factors,
  homeSnap,
  awaySnap,
}: {
  zone: ZoneInfo;
  homeTeam: string;
  awayTeam: string;
  mode: HeatMode;
  factors: GoalModelFactors | null;
  homeSnap: KxlTeamSnapshot | null;
  awaySnap: KxlTeamSnapshot | null;
}) {
  const { col, depth, homeVal, awayVal } = zone;
  const depthLabel = DEPTH_LABELS[depth];
  const corrLabel = CORR_LABELS[col];

  const sourceMap: Record<number, string> = {
    0: factors
      ? `DNA setorial · Ataque KXL · λ casa=${factors.lambdaHome.toFixed(2)}`
      : "DNA setorial · Ataque KXL",
    1: homeSnap
      ? `Posse real ${homeSnap.possessionPct.toFixed(1)}% × Ataque × Contra-ataque`
      : "Posse × Ataque KXL × Contra-ataque",
    2: homeSnap
      ? `Posse real ${homeSnap.possessionPct.toFixed(1)}% × Controle ${(homeSnap.controlIndex * 100).toFixed(0)}`
      : "Posse × Controle KXL",
    3: `Defesa KXL · Permissividade setorial`,
  };

  return (
    <div className="space-y-2 text-xs">
      <p className="font-semibold text-white">
        {depthLabel} · {corrLabel}
      </p>
      <div className="space-y-1 text-slate-400">
        <div className="flex items-center justify-between">
          <span style={{ color: outcomeColors["1"] }}>{homeTeam}</span>
          <div className="flex items-center gap-2">
            <div className="h-2 rounded-full bg-neon-green/30" style={{ width: `${homeVal * 60}px` }} />
            <span className="font-mono text-white">{(homeVal * 100).toFixed(0)}%</span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span style={{ color: outcomeColors["2"] }}>{awayTeam}</span>
          <div className="flex items-center gap-2">
            <div className="h-2 rounded-full bg-neon-purple/30" style={{ width: `${awayVal * 60}px` }} />
            <span className="font-mono text-white">{(awayVal * 100).toFixed(0)}%</span>
          </div>
        </div>
        {mode === "duelo" && (
          <p
            className={`border-t border-white/10 pt-1 ${
              homeVal > awayVal
                ? "text-neon-green"
                : homeVal < awayVal
                  ? "text-neon-purple"
                  : "text-slate-400"
            }`}
          >
            {homeVal > awayVal
              ? `${homeTeam} domina (+${((homeVal - awayVal) * 100).toFixed(0)}pp)`
              : homeVal < awayVal
                ? `${awayTeam} domina (+${((awayVal - homeVal) * 100).toFixed(0)}pp)`
                : "Disputa equilibrada"}
          </p>
        )}
        {homeSnap && awaySnap && depth === 1 && (
          <p className="border-t border-white/10 pt-1 text-[10px] text-slate-500">
            Posse real: {homeTeam} {homeSnap.possessionPct.toFixed(1)}% ·{" "}
            {awayTeam} {awaySnap.possessionPct.toFixed(1)}%
          </p>
        )}
      </div>
      <p className="text-[10px] text-slate-600">Fonte: {sourceMap[depth] ?? "KXL"}</p>
    </div>
  );
}

function ModeBtn({
  active,
  onClick,
  label,
  color,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  color?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
        active ? "text-white" : "border border-white/10 bg-white/5 text-slate-400 hover:bg-white/10"
      }`}
      style={
        active
          ? {
              borderWidth: 1,
              borderStyle: "solid",
              borderColor: color ? `${color}50` : "rgba(0,212,255,0.45)",
              backgroundColor: color ? `${color}15` : "rgba(0,212,255,0.10)",
              color: color ?? "#00d4ff",
            }
          : undefined
      }
    >
      {label}
    </button>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="inline-block h-2.5 w-6 rounded-sm" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

function DataSourcesNote({
  prediction,
  homeSnap,
  possSource,
}: {
  prediction: WcPrediction;
  homeSnap: KxlTeamSnapshot | null;
  possSource: string;
}) {
  const parts: string[] = [possSource];

  if (prediction.modelBreakdown.kxlCollision)
    parts.push("DNA setorial KXL Fase 3");

  if (prediction.modelBreakdown.poissonFactors) {
    const f = prediction.modelBreakdown.poissonFactors;
    parts.push(`λ Dixon-Coles: casa ${f.lambdaHome.toFixed(2)} · fora ${f.lambdaAway.toFixed(2)}`);
  }

  if (homeSnap) {
    parts.push(
      `Ataque ${(homeSnap.attackIndex * 100).toFixed(0)} · Def ${(homeSnap.defenseIndex * 100).toFixed(0)} · Ctrl ${(homeSnap.controlIndex * 100).toFixed(0)}`,
    );
  }

  return (
    <p className="text-center text-[10px] leading-relaxed text-slate-600">
      {parts.join(" · ")}
    </p>
  );
}
