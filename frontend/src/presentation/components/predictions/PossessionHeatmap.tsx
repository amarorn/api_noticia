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

import { useId, useMemo, useState } from "react";
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

const DEPTH_SHORT = ["Caixa", "Ofensivo", "Meio", "Defesa"] as const;

// ─── Cores e preenchimento ─────────────────────────────────────────────────────

function zoneIntensity(
  mode: HeatMode,
  homeVal: number,
  awayVal: number,
  rawVal: number,
  maxVal: number,
): number {
  if (mode === "duelo") return Math.abs(homeVal - awayVal) / maxVal;
  return rawVal / maxVal;
}

function zoneFillUrl(
  intensity: number,
  mode: HeatMode,
  homeVal: number,
  awayVal: number,
  uid: string,
): string {
  if (intensity < 0.04) return "transparent";
  if (mode === "home") return `url(#${uid}-team-home)`;
  if (mode === "away") return `url(#${uid}-team-away)`;
  const net = homeVal - awayVal;
  if (net > 0.04) return `url(#${uid}-home)`;
  if (net < -0.04) return `url(#${uid}-away)`;
  return `url(#${uid}-neutral)`;
}

// ─── Componente principal ──────────────────────────────────────────────────────

export interface PossessionHeatmapProps {
  prediction: WcPrediction;
  className?: string;
}

export function PossessionHeatmap({ prediction, className = "" }: PossessionHeatmapProps) {
  const uid = useId().replace(/:/g, "");
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

  const PITCH_W = 108;
  const PITCH_H = 168;
  const PAD = 3;
  const LABEL_W = 8;
  const INNER_W = PITCH_W - PAD * 2 - LABEL_W;
  const INNER_H = PITCH_H - PAD * 2;
  const ZONE_W = INNER_W / 3;
  const ZONE_H = INNER_H / 4;
  const ORIGIN_X = PAD;

  const attackTeam = mode === "away" ? prediction.awayTeam : prediction.homeTeam;
  const defendTeam = mode === "away" ? prediction.homeTeam : prediction.awayTeam;
  const attackColor = mode === "away" ? outcomeColors["2"] : outcomeColors["1"];

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

      <div className="relative mx-auto max-w-sm">
        <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-surface/40 p-2 shadow-[0_8px_32px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.06)]">
          <svg
            viewBox={`0 0 ${PITCH_W} ${PITCH_H}`}
            className="w-full select-none"
            role="img"
            aria-label="Mapa de posse de bola por zona do gramado"
          >
            <defs>
              <linearGradient id={`${uid}-grass`} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#0f2a1a" />
                <stop offset="35%" stopColor="#1a4a2e" />
                <stop offset="65%" stopColor="#1e5534" />
                <stop offset="100%" stopColor="#0f2a1a" />
              </linearGradient>

              <pattern
                id={`${uid}-stripes`}
                width="8"
                height={INNER_H}
                patternUnits="userSpaceOnUse"
                x={ORIGIN_X}
                y={PAD}
              >
                <rect width="4" height={INNER_H} fill="rgba(255,255,255,0.025)" />
                <rect x="4" width="4" height={INNER_H} fill="rgba(0,0,0,0.04)" />
              </pattern>

              <radialGradient id={`${uid}-home`} cx="50%" cy="50%" r="70%">
                <stop offset="0%" stopColor="rgba(0,255,136,0.6)" />
                <stop offset="60%" stopColor="rgba(0,255,136,0.2)" />
                <stop offset="100%" stopColor="rgba(0,255,136,0)" />
              </radialGradient>
              <radialGradient id={`${uid}-away`} cx="50%" cy="50%" r="70%">
                <stop offset="0%" stopColor="rgba(168,85,247,0.6)" />
                <stop offset="60%" stopColor="rgba(168,85,247,0.2)" />
                <stop offset="100%" stopColor="rgba(168,85,247,0)" />
              </radialGradient>
              <radialGradient id={`${uid}-neutral`} cx="50%" cy="50%" r="70%">
                <stop offset="0%" stopColor="rgba(0,212,255,0.4)" />
                <stop offset="60%" stopColor="rgba(0,212,255,0.14)" />
                <stop offset="100%" stopColor="rgba(0,212,255,0)" />
              </radialGradient>
              <radialGradient id={`${uid}-team-home`} cx="50%" cy="50%" r="70%">
                <stop offset="0%" stopColor={outcomeColors["1"]} stopOpacity="0.55" />
                <stop offset="60%" stopColor={outcomeColors["1"]} stopOpacity="0.18" />
                <stop offset="100%" stopColor={outcomeColors["1"]} stopOpacity="0" />
              </radialGradient>
              <radialGradient id={`${uid}-team-away`} cx="50%" cy="50%" r="70%">
                <stop offset="0%" stopColor={outcomeColors["2"]} stopOpacity="0.55" />
                <stop offset="60%" stopColor={outcomeColors["2"]} stopOpacity="0.18" />
                <stop offset="100%" stopColor={outcomeColors["2"]} stopOpacity="0" />
              </radialGradient>

              <linearGradient id={`${uid}-vignette`} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="rgba(0,0,0,0.3)" />
                <stop offset="12%" stopColor="rgba(0,0,0,0)" />
                <stop offset="88%" stopColor="rgba(0,0,0,0)" />
                <stop offset="100%" stopColor="rgba(0,0,0,0.35)" />
              </linearGradient>

              <filter id={`${uid}-glow`} x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="1" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Gramado */}
            <rect
              x={ORIGIN_X}
              y={PAD}
              width={INNER_W}
              height={INNER_H}
              rx="1.5"
              fill={`url(#${uid}-grass)`}
            />
            <rect
              x={ORIGIN_X}
              y={PAD}
              width={INNER_W}
              height={INNER_H}
              rx="1.5"
              fill={`url(#${uid}-stripes)`}
            />

            {/* Zonas de calor */}
            {[0, 1, 2, 3].map((depth) =>
              [0, 1, 2].map((col) => {
                const homeVal = homeZones[depth]?.[col] ?? 0;
                const awayVal = awayZones[depth]?.[col] ?? 0;
                const rawVal = mode === "away" ? awayVal : homeVal;
                const intensity = zoneIntensity(mode, homeVal, awayVal, rawVal, maxVal);
                const fill = zoneFillUrl(intensity, mode, homeVal, awayVal, uid);
                const x = ORIGIN_X + col * ZONE_W;
                const y = PAD + depth * ZONE_H;
                const isActive = activeZone?.col === col && activeZone?.depth === depth;

                return (
                  <g key={`z-${depth}-${col}`}>
                    <motion.rect
                      x={x + 0.4}
                      y={y + 0.4}
                      width={ZONE_W - 0.8}
                      height={ZONE_H - 0.8}
                      rx="0.6"
                      fill={fill}
                      className="cursor-pointer"
                      initial={false}
                      animate={{
                        opacity:
                          intensity < 0.04
                            ? 0
                            : isActive
                              ? 0.95
                              : 0.3 + intensity * 0.55,
                      }}
                      transition={{ duration: 0.22 }}
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
                    {isActive && intensity >= 0.04 && (
                      <rect
                        x={x + 0.4}
                        y={y + 0.4}
                        width={ZONE_W - 0.8}
                        height={ZONE_H - 0.8}
                        rx="0.6"
                        fill="none"
                        stroke="rgba(255,255,255,0.55)"
                        strokeWidth="0.45"
                        filter={`url(#${uid}-glow)`}
                        pointerEvents="none"
                      />
                    )}
                  </g>
                );
              }),
            )}

            {/* Marcacoes do campo */}
            <g pointerEvents="none" fill="none" stroke="rgba(255,255,255,0.28)">
              <rect
                x={ORIGIN_X}
                y={PAD}
                width={INNER_W}
                height={INNER_H}
                rx="1.5"
                strokeWidth="0.55"
              />
              <line
                x1={ORIGIN_X}
                y1={PAD + INNER_H / 2}
                x2={ORIGIN_X + INNER_W}
                y2={PAD + INNER_H / 2}
                stroke="rgba(255,255,255,0.2)"
                strokeWidth="0.45"
              />
              <circle
                cx={ORIGIN_X + INNER_W / 2}
                cy={PAD + INNER_H / 2}
                r="9"
                strokeWidth="0.4"
                stroke="rgba(255,255,255,0.18)"
              />
              <circle
                cx={ORIGIN_X + INNER_W / 2}
                cy={PAD + INNER_H / 2}
                r="0.7"
                fill="rgba(255,255,255,0.35)"
                stroke="none"
              />
              <rect
                x={ORIGIN_X + INNER_W / 2 - 16}
                y={PAD}
                width="32"
                height="13"
                strokeWidth="0.38"
                stroke="rgba(255,255,255,0.16)"
              />
              <rect
                x={ORIGIN_X + INNER_W / 2 - 10}
                y={PAD}
                width="20"
                height="5"
                strokeWidth="0.3"
                stroke="rgba(255,255,255,0.1)"
              />
              <circle
                cx={ORIGIN_X + INNER_W / 2}
                cy={PAD + 9}
                r="0.65"
                fill="rgba(255,255,255,0.3)"
                stroke="none"
              />
              <rect
                x={ORIGIN_X + INNER_W / 2 - 16}
                y={PAD + INNER_H - 13}
                width="32"
                height="13"
                strokeWidth="0.38"
                stroke="rgba(255,255,255,0.16)"
              />
              <rect
                x={ORIGIN_X + INNER_W / 2 - 10}
                y={PAD + INNER_H - 5}
                width="20"
                height="5"
                strokeWidth="0.3"
                stroke="rgba(255,255,255,0.1)"
              />
              <circle
                cx={ORIGIN_X + INNER_W / 2}
                cy={PAD + INNER_H - 9}
                r="0.65"
                fill="rgba(255,255,255,0.3)"
                stroke="none"
              />
              <rect
                x={ORIGIN_X + INNER_W / 2 - 8}
                y={PAD - 0.5}
                width="16"
                height="1.2"
                fill="rgba(255,255,255,0.12)"
                stroke="rgba(255,255,255,0.3)"
                strokeWidth="0.35"
              />
              <rect
                x={ORIGIN_X + INNER_W / 2 - 8}
                y={PAD + INNER_H - 0.7}
                width="16"
                height="1.2"
                fill="rgba(255,255,255,0.12)"
                stroke="rgba(255,255,255,0.3)"
                strokeWidth="0.35"
              />
              {[1, 2].map((n) => (
                <line
                  key={n}
                  x1={ORIGIN_X + n * ZONE_W}
                  y1={PAD + 12}
                  x2={ORIGIN_X + n * ZONE_W}
                  y2={PAD + INNER_H - 12}
                  stroke="rgba(255,255,255,0.06)"
                  strokeWidth="0.35"
                  strokeDasharray="1.5,2.5"
                />
              ))}
              {[1, 2, 3].map((n) => (
                <line
                  key={`d-${n}`}
                  x1={ORIGIN_X + 1}
                  y1={PAD + n * ZONE_H}
                  x2={ORIGIN_X + INNER_W - 1}
                  y2={PAD + n * ZONE_H}
                  stroke="rgba(255,255,255,0.04)"
                  strokeWidth="0.25"
                  strokeDasharray="2,3"
                />
              ))}
            </g>

            {/* Labels corredores (topo) */}
            {CORR_LABELS.map((label, col) => {
              const cx = ORIGIN_X + col * ZONE_W + ZONE_W / 2;
              return (
                <g key={`corr-${col}`} pointerEvents="none">
                  <rect
                    x={cx - 9}
                    y={PAD + 2.5}
                    width="18"
                    height="5"
                    rx="2.5"
                    fill="rgba(0,0,0,0.35)"
                    stroke="rgba(255,255,255,0.06)"
                    strokeWidth="0.2"
                  />
                  <text
                    x={cx}
                    y={PAD + 6}
                    textAnchor="middle"
                    fill="rgba(255,255,255,0.5)"
                    fontSize="2.6"
                    fontWeight="600"
                    letterSpacing="0.06em"
                  >
                    {label.toUpperCase()}
                  </text>
                </g>
              );
            })}

            {/* Labels profundidade (direita) */}
            {DEPTH_LABELS.map((label, depth) => {
              const cy = PAD + depth * ZONE_H + ZONE_H / 2;
              const isActive = activeZone?.depth === depth;
              return (
                <g key={`depth-${depth}`} pointerEvents="none">
                  <rect
                    x={ORIGIN_X + INNER_W + 0.5}
                    y={cy - 4}
                    width={LABEL_W - 1}
                    height="8"
                    rx="2"
                    fill={isActive ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.4)"}
                    stroke={isActive ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.05)"}
                    strokeWidth="0.2"
                  />
                  <text
                    x={ORIGIN_X + INNER_W + LABEL_W / 2}
                    y={cy + 0.8}
                    textAnchor="middle"
                    fill={isActive ? "rgba(255,255,255,0.85)" : "rgba(255,255,255,0.4)"}
                    fontSize="2.2"
                    fontWeight="600"
                  >
                    {DEPTH_SHORT[depth]}
                  </text>
                  <title>{label}</title>
                </g>
              );
            })}

            {/* Badge time atacante (topo) */}
            <g pointerEvents="none">
              <rect
                x={ORIGIN_X + INNER_W / 2 - 18}
                y={PAD - 0.5}
                width="36"
                height="0"
                fill="none"
              />
              <rect
                x={ORIGIN_X + INNER_W / 2 - 16}
                y={0.5}
                width="32"
                height="5.5"
                rx="2.75"
                fill="rgba(0,0,0,0.45)"
                stroke={`${attackColor}40`}
                strokeWidth="0.3"
              />
              <text
                x={ORIGIN_X + INNER_W / 2}
                y={4.2}
                textAnchor="middle"
                fill="rgba(255,255,255,0.9)"
                fontSize="2.8"
                fontWeight="700"
                letterSpacing="0.06em"
              >
                {attackTeam.slice(0, 14).toUpperCase()}
              </text>
            </g>

            {/* Badge time defensor (base) */}
            <g pointerEvents="none">
              <rect
                x={ORIGIN_X + INNER_W / 2 - 14}
                y={PITCH_H - 5.5}
                width="28"
                height="5"
                rx="2.5"
                fill="rgba(0,0,0,0.4)"
                stroke="rgba(255,255,255,0.06)"
                strokeWidth="0.2"
              />
              <text
                x={ORIGIN_X + INNER_W / 2}
                y={PITCH_H - 2.2}
                textAnchor="middle"
                fill="rgba(255,255,255,0.45)"
                fontSize="2.5"
                fontWeight="500"
              >
                {defendTeam.slice(0, 14)}
              </text>
            </g>

            {/* Vignette */}
            <rect
              x={ORIGIN_X}
              y={PAD}
              width={INNER_W}
              height={INNER_H}
              rx="1.5"
              fill={`url(#${uid}-vignette)`}
              pointerEvents="none"
            />
          </svg>
        </div>

        <AnimatePresence>
          {activeZone && (
            <motion.div
              key="tooltip"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.2 }}
              className="absolute bottom-3 left-3 right-3 rounded-xl border border-white/12 bg-surface/95 p-3 shadow-2xl backdrop-blur-md"
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

      <div className="mx-auto flex max-w-sm flex-wrap items-center justify-center gap-x-4 gap-y-1.5">
        <LegendDot color="#00ff88" label={prediction.homeTeam} />
        <LegendDot color="#00d4ff" label="Neutro" />
        <LegendDot color="#a855f7" label={prediction.awayTeam} />
      </div>

      <p className="text-center text-[11px] text-slate-500">
        Passe o mouse ou toque em uma zona para ver posse estimada
      </p>

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
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="mb-2.5 flex items-center justify-between gap-2 text-xs">
        <span className="font-display font-semibold" style={{ color: outcomeColors["1"] }}>
          {homeTeam}
        </span>
        <span className="truncate text-[10px] text-slate-600">{source}</span>
        <span className="font-display font-semibold" style={{ color: outcomeColors["2"] }}>
          {awayTeam}
        </span>
      </div>
      <div className="relative flex h-8 overflow-hidden rounded-xl border border-white/[0.08] shadow-inner">
        <div
          className="flex items-center justify-center text-xs font-bold transition-all duration-700"
          style={{
            width: `${homePct * 100}%`,
            background: `linear-gradient(90deg, ${outcomeColors["1"]}25, ${outcomeColors["1"]}50)`,
            color: outcomeColors["1"],
            boxShadow: `inset 0 0 20px ${outcomeColors["1"]}20`,
          }}
        >
          {homePctInt}%
        </div>
        <div
          className="flex items-center justify-center text-xs font-bold transition-all duration-700"
          style={{
            width: `${awayPct * 100}%`,
            background: `linear-gradient(90deg, ${outcomeColors["2"]}50, ${outcomeColors["2"]}25)`,
            color: outcomeColors["2"],
            boxShadow: `inset 0 0 20px ${outcomeColors["2"]}20`,
          }}
        >
          {awayPctInt}%
        </div>
        <div className="pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-white/10" />
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
      <p className="font-display font-semibold text-white">
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
      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
        active
          ? "border text-white shadow-sm"
          : "border border-white/10 bg-white/[0.04] text-slate-400 hover:border-white/15 hover:bg-white/[0.07]"
      }`}
      style={
        active && color
          ? {
              borderColor: `${color}50`,
              backgroundColor: `${color}14`,
              color,
              boxShadow: `0 0 20px ${color}18`,
            }
          : active
            ? {
                borderColor: "rgba(0,212,255,0.45)",
                backgroundColor: "rgba(0,212,255,0.1)",
                boxShadow: "0 0 20px rgba(0,212,255,0.1)",
              }
            : undefined
      }
    >
      {label}
    </button>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[10px] text-slate-500">
      <span
        className="h-2 w-2 rounded-full shadow-[0_0_6px_currentColor]"
        style={{ backgroundColor: color, color }}
      />
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
