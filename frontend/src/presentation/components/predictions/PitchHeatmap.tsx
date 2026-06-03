import { useId, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { outcomeColors } from "@/presentation/theme";

export type PitchSectorId = "esquerda" | "meio" | "direita";

export interface PitchSectorMetric {
  id: PitchSectorId;
  label: string;
  colisao: number;
  attackDna?: number;
  permissividade?: number;
}

export type PitchViewMode = "home" | "away" | "duel";

type DuelSectorMetric = PitchSectorMetric & {
  homeColisao: number;
  awayColisao: number;
  net: number;
};

interface PitchHeatmapProps {
  homeTeam: string;
  awayTeam: string;
  homeSectors: PitchSectorMetric[];
  awaySectors: PitchSectorMetric[];
  className?: string;
}

const SECTOR_ORDER: PitchSectorId[] = ["esquerda", "meio", "direita"];

const SECTOR_LABELS: Record<PitchSectorId, string> = {
  esquerda: "Esquerda",
  meio: "Meio",
  direita: "Direita",
};

const SECTOR_SHORT: Record<PitchSectorId, string> = {
  esquerda: "Esq.",
  meio: "Centro",
  direita: "Dir.",
};

function orderSectors(list: PitchSectorMetric[]): PitchSectorMetric[] {
  const map = new Map(list.map((s) => [s.id, s]));
  return SECTOR_ORDER.map((id) => {
    const found = map.get(id);
    return (
      found ?? {
        id,
        label: SECTOR_LABELS[id],
        colisao: 0,
      }
    );
  });
}

function sectorFill(
  intensity: number,
  mode: PitchViewMode,
  net: number,
  gradId: string,
): string {
  if (intensity < 0.04) return "transparent";
  if (mode === "duel") {
    if (net > 0.05) return `url(#${gradId}-home)`;
    if (net < -0.05) return `url(#${gradId}-away)`;
    return `url(#${gradId}-neutral)`;
  }
  return `url(#${gradId}-team)`;
}

export function PitchHeatmap({
  homeTeam,
  awayTeam,
  homeSectors,
  awaySectors,
  className = "",
}: PitchHeatmapProps) {
  const uid = useId().replace(/:/g, "");
  const [mode, setMode] = useState<PitchViewMode>("duel");
  const [activeId, setActiveId] = useState<PitchSectorId | null>(null);

  const homeOrdered = useMemo(() => orderSectors(homeSectors), [homeSectors]);
  const awayOrdered = useMemo(() => orderSectors(awaySectors), [awaySectors]);

  const duelSectors = useMemo((): DuelSectorMetric[] => {
    const maxH = Math.max(...homeOrdered.map((s) => s.colisao), 0.01);
    const maxA = Math.max(...awayOrdered.map((s) => s.colisao), 0.01);
    return SECTOR_ORDER.map((id) => {
      const h = homeOrdered.find((s) => s.id === id)!;
      const a = awayOrdered.find((s) => s.id === id)!;
      const nh = h.colisao / maxH;
      const na = a.colisao / maxA;
      return {
        id,
        label: SECTOR_LABELS[id],
        colisao: h.colisao - a.colisao,
        attackDna: h.attackDna,
        permissividade: a.permissividade,
        homeColisao: h.colisao,
        awayColisao: a.colisao,
        net: nh - na,
      };
    });
  }, [homeOrdered, awayOrdered]);

  const displaySectors: PitchSectorMetric[] | DuelSectorMetric[] =
    mode === "home" ? homeOrdered : mode === "away" ? awayOrdered : duelSectors;

  const intensities = useMemo(() => {
    if (mode === "duel") {
      const nets = duelSectors.map((s) => Math.abs(s.net));
      const max = Math.max(...nets, 0.01);
      return duelSectors.map((s) => Math.abs(s.net) / max);
    }
    const list = mode === "home" ? homeOrdered : awayOrdered;
    const max = Math.max(...list.map((s) => s.colisao), 0.01);
    return list.map((s) => s.colisao / max);
  }, [mode, duelSectors, homeOrdered, awayOrdered]);

  const teamColor =
    mode === "home"
      ? outcomeColors["1"]
      : mode === "away"
        ? outcomeColors["2"]
        : "#00d4ff";

  const attackingTeam =
    mode === "home" ? homeTeam : mode === "away" ? awayTeam : null;

  const activeSector = activeId
    ? displaySectors.find((s) => s.id === activeId)
    : null;

  const PITCH_W = 100;
  const PITCH_H = 152;
  const PAD = 3;
  const INNER_W = PITCH_W - PAD * 2;
  const INNER_H = PITCH_H - PAD * 2;
  const COL_W = INNER_W / 3;

  return (
    <div className={`space-y-4 ${className}`}>
      <div className="flex flex-wrap gap-2">
        <ModeButton
          active={mode === "duel"}
          onClick={() => setMode("duel")}
          label="Duelo setorial"
        />
        <ModeButton
          active={mode === "home"}
          onClick={() => setMode("home")}
          label={homeTeam}
          color={outcomeColors["1"]}
        />
        <ModeButton
          active={mode === "away"}
          onClick={() => setMode("away")}
          label={awayTeam}
          color={outcomeColors["2"]}
        />
      </div>

      <div className="relative mx-auto max-w-sm">
        <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-surface/40 p-2 shadow-[0_8px_32px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.06)]">
          <svg
            viewBox={`0 0 ${PITCH_W} ${PITCH_H}`}
            className="w-full select-none"
            role="img"
            aria-label="Mapa de calor do gramado por setor"
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
                x={PAD}
                y={PAD}
              >
                <rect width="4" height={INNER_H} fill="rgba(255,255,255,0.025)" />
                <rect x="4" width="4" height={INNER_H} fill="rgba(0,0,0,0.04)" />
              </pattern>

              <radialGradient id={`${uid}-home`} cx="50%" cy="85%" r="75%">
                <stop offset="0%" stopColor="rgba(0,255,136,0.55)" />
                <stop offset="55%" stopColor="rgba(0,255,136,0.22)" />
                <stop offset="100%" stopColor="rgba(0,255,136,0)" />
              </radialGradient>
              <radialGradient id={`${uid}-away`} cx="50%" cy="85%" r="75%">
                <stop offset="0%" stopColor="rgba(168,85,247,0.55)" />
                <stop offset="55%" stopColor="rgba(168,85,247,0.22)" />
                <stop offset="100%" stopColor="rgba(168,85,247,0)" />
              </radialGradient>
              <radialGradient id={`${uid}-neutral`} cx="50%" cy="85%" r="75%">
                <stop offset="0%" stopColor="rgba(0,212,255,0.35)" />
                <stop offset="55%" stopColor="rgba(0,212,255,0.12)" />
                <stop offset="100%" stopColor="rgba(0,212,255,0)" />
              </radialGradient>
              <radialGradient id={`${uid}-team`} cx="50%" cy="85%" r="75%">
                <stop offset="0%" stopColor={teamColor} stopOpacity="0.5" />
                <stop offset="55%" stopColor={teamColor} stopOpacity="0.18" />
                <stop offset="100%" stopColor={teamColor} stopOpacity="0" />
              </radialGradient>

              <linearGradient id={`${uid}-vignette`} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="rgba(0,0,0,0.35)" />
                <stop offset="15%" stopColor="rgba(0,0,0,0)" />
                <stop offset="85%" stopColor="rgba(0,0,0,0)" />
                <stop offset="100%" stopColor="rgba(0,0,0,0.4)" />
              </linearGradient>

              <filter id={`${uid}-glow`} x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="1.2" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Gramado base */}
            <rect
              x={PAD}
              y={PAD}
              width={INNER_W}
              height={INNER_H}
              rx="1.5"
              fill={`url(#${uid}-grass)`}
            />
            <rect
              x={PAD}
              y={PAD}
              width={INNER_W}
              height={INNER_H}
              rx="1.5"
              fill={`url(#${uid}-stripes)`}
            />

            {/* Calor por setor */}
            {displaySectors.map((sector, i) => {
              const x = PAD + i * COL_W;
              const intensity = intensities[i];
              const isActive = activeId === sector.id;
              const duelSector = mode === "duel" ? (sector as DuelSectorMetric) : null;
              const net = duelSector?.net ?? 0;
              const fill = sectorFill(intensity, mode, net, uid);

              return (
                <g key={sector.id}>
                  <motion.rect
                    x={x + 0.5}
                    y={PAD + 0.5}
                    width={COL_W - 1}
                    height={INNER_H - 1}
                    fill={fill}
                    opacity={intensity < 0.04 ? 0 : 0.35 + intensity * 0.65}
                    className="cursor-pointer"
                    initial={false}
                    animate={{
                      opacity:
                        intensity < 0.04
                          ? 0
                          : isActive
                            ? 0.95
                            : 0.35 + intensity * 0.55,
                    }}
                    transition={{ duration: 0.25 }}
                    onMouseEnter={() => setActiveId(sector.id)}
                    onMouseLeave={() => setActiveId(null)}
                    onClick={() =>
                      setActiveId((prev) => (prev === sector.id ? null : sector.id))
                    }
                  />
                  {isActive && intensity >= 0.04 && (
                    <rect
                      x={x + 0.5}
                      y={PAD + 0.5}
                      width={COL_W - 1}
                      height={INNER_H - 1}
                      fill="none"
                      stroke="rgba(255,255,255,0.55)"
                      strokeWidth="0.5"
                      filter={`url(#${uid}-glow)`}
                      pointerEvents="none"
                    />
                  )}
                </g>
              );
            })}

            {/* Marcacoes do campo (camada superior) */}
            <g pointerEvents="none" stroke="rgba(255,255,255,0.28)" fill="none">
              <rect
                x={PAD}
                y={PAD}
                width={INNER_W}
                height={INNER_H}
                rx="1.5"
                strokeWidth="0.55"
              />
              <line
                x1={PAD}
                y1={PITCH_H / 2}
                x2={PITCH_W - PAD}
                y2={PITCH_H / 2}
                strokeWidth="0.45"
                stroke="rgba(255,255,255,0.22)"
              />
              <circle
                cx={PITCH_W / 2}
                cy={PITCH_H / 2}
                r="9"
                strokeWidth="0.4"
                stroke="rgba(255,255,255,0.2)"
              />
              <circle
                cx={PITCH_W / 2}
                cy={PITCH_H / 2}
                r="0.7"
                fill="rgba(255,255,255,0.35)"
                stroke="none"
              />
              {/* Area superior */}
              <rect x="34" y={PAD} width="32" height="13" strokeWidth="0.38" stroke="rgba(255,255,255,0.18)" />
              <rect x="40" y={PAD} width="20" height="5" strokeWidth="0.3" stroke="rgba(255,255,255,0.12)" />
              <circle cx={PITCH_W / 2} cy={PAD + 9} r="0.65" fill="rgba(255,255,255,0.3)" stroke="none" />
              {/* Area inferior */}
              <rect x="34" y={PITCH_H - PAD - 13} width="32" height="13" strokeWidth="0.38" stroke="rgba(255,255,255,0.18)" />
              <rect x="40" y={PITCH_H - PAD - 5} width="20" height="5" strokeWidth="0.3" stroke="rgba(255,255,255,0.12)" />
              <circle cx={PITCH_W / 2} cy={PITCH_H - PAD - 9} r="0.65" fill="rgba(255,255,255,0.3)" stroke="none" />
              {/* Traves */}
              <rect x="42" y={PAD - 0.5} width="16" height="1.2" fill="rgba(255,255,255,0.15)" stroke="rgba(255,255,255,0.35)" strokeWidth="0.35" />
              <rect x="42" y={PITCH_H - PAD - 0.7} width="16" height="1.2" fill="rgba(255,255,255,0.15)" stroke="rgba(255,255,255,0.35)" strokeWidth="0.35" />
              {/* Divisores verticais */}
              {[1, 2].map((n) => (
                <line
                  key={n}
                  x1={PAD + n * COL_W}
                  y1={PAD + 14}
                  x2={PAD + n * COL_W}
                  y2={PITCH_H - PAD - 14}
                  stroke="rgba(255,255,255,0.06)"
                  strokeWidth="0.35"
                  strokeDasharray="1.5,2.5"
                />
              ))}
            </g>

            {/* Labels dos setores */}
            {SECTOR_ORDER.map((id, i) => {
              const x = PAD + i * COL_W + COL_W / 2;
              const isActive = activeId === id;
              const intensity = intensities[i];
              return (
                <g key={`label-${id}`} pointerEvents="none">
                  <rect
                    x={x - 11}
                    y={PAD + 3}
                    width="22"
                    height="5.5"
                    rx="2.75"
                    fill={isActive ? "rgba(255,255,255,0.14)" : "rgba(0,0,0,0.35)"}
                    stroke={isActive ? "rgba(255,255,255,0.25)" : "rgba(255,255,255,0.06)"}
                    strokeWidth="0.25"
                  />
                  <text
                    x={x}
                    y={PAD + 6.8}
                    textAnchor="middle"
                    fill={isActive ? "rgba(255,255,255,0.95)" : "rgba(255,255,255,0.55)"}
                    fontSize="2.8"
                    fontWeight="600"
                    letterSpacing="0.08em"
                  >
                    {SECTOR_SHORT[id].toUpperCase()}
                  </text>
                  {intensity >= 0.15 && (
                    <text
                      x={x}
                      y={PITCH_H - PAD - 4}
                      textAnchor="middle"
                      fill="rgba(255,255,255,0.35)"
                      fontSize="2.6"
                      fontWeight="500"
                    >
                      {Math.round(intensity * 100)}%
                    </text>
                  )}
                </g>
              );
            })}

            {/* Vignette */}
            <rect
              x={PAD}
              y={PAD}
              width={INNER_W}
              height={INNER_H}
              rx="1.5"
              fill={`url(#${uid}-vignette)`}
              pointerEvents="none"
            />

            {/* Indicador de ataque */}
            {attackingTeam && (
              <g pointerEvents="none">
                <polygon
                  points={`${PITCH_W / 2},${PITCH_H - PAD + 1} ${PITCH_W / 2 - 3.5},${PITCH_H - PAD + 5} ${PITCH_W / 2 + 3.5},${PITCH_H - PAD + 5}`}
                  fill={teamColor}
                  opacity="0.85"
                />
                <text
                  x={PITCH_W / 2}
                  y={PITCH_H - 0.5}
                  textAnchor="middle"
                  fill="rgba(255,255,255,0.7)"
                  fontSize="2.8"
                  fontWeight="600"
                >
                  {attackingTeam.slice(0, 14)}
                </text>
              </g>
            )}
          </svg>
        </div>

        <AnimatePresence>
          {activeSector && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.2 }}
              className="absolute bottom-3 left-3 right-3 rounded-xl border border-white/12 bg-surface/95 p-3 shadow-2xl backdrop-blur-md"
            >
              <SectorTooltip
                sector={activeSector}
                mode={mode}
                homeTeam={homeTeam}
                awayTeam={awayTeam}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="mx-auto flex max-w-sm flex-wrap items-center justify-center gap-x-4 gap-y-1.5">
        <LegendDot color="#00ff88" label={homeTeam} />
        <LegendDot color="#a855f7" label={awayTeam} />
        <LegendDot color="#00d4ff" label="Equilibrado" />
      </div>
      <p className="text-center text-[11px] text-slate-500">
        Passe o mouse ou toque em um corredor para ver colisão setorial
      </p>
    </div>
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

function ModeButton({
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

function SectorTooltip({
  sector,
  mode,
  homeTeam,
  awayTeam,
}: {
  sector: PitchSectorMetric | DuelSectorMetric;
  mode: PitchViewMode;
  homeTeam: string;
  awayTeam: string;
}) {
  const duel = mode === "duel" ? (sector as DuelSectorMetric) : null;
  return (
    <div className="text-xs">
      <p className="font-display font-semibold text-white">
        Corredor {sector.label}
      </p>
      {duel && (
        <ul className="mt-2 space-y-1 text-slate-400">
          <li>
            <span className="text-neon-green">{homeTeam}</span> colisão:{" "}
            <span className="font-mono text-white">{duel.homeColisao.toFixed(2)}</span>
          </li>
          <li>
            <span className="text-neon-purple">{awayTeam}</span> colisão:{" "}
            <span className="font-mono text-white">{duel.awayColisao.toFixed(2)}</span>
          </li>
          <li className="border-t border-white/10 pt-1 text-slate-300">
            Saldo:{" "}
            <span
              className={
                duel.net > 0 ? "text-neon-green" : duel.net < 0 ? "text-neon-purple" : ""
              }
            >
              {duel.net > 0 ? "+" : ""}
              {duel.net.toFixed(2)}
            </span>
          </li>
        </ul>
      )}
      {mode !== "duel" && (
        <p className="mt-1 text-slate-400">
          Índice de colisão:{" "}
          <span className="font-mono font-semibold text-white">
            {sector.colisao.toFixed(2)}
          </span>
        </p>
      )}
      {sector.attackDna != null && (
        <p className="mt-1 text-slate-500">DNA ataque: {sector.attackDna.toFixed(2)}</p>
      )}
      {sector.permissividade != null && (
        <p className="text-slate-500">
          Permissividade def.: {(sector.permissividade * 100).toFixed(0)}%
        </p>
      )}
    </div>
  );
}

/** Monta setores a partir do breakdown de colisão da API. */
export function sectorsFromCollision(
  setores: {
    setor: string;
    colisao: number;
    attackDna?: number;
    permissividade?: number;
  }[],
): PitchSectorMetric[] {
  const idMap: Record<string, PitchSectorId> = {
    esquerda: "esquerda",
    direita: "direita",
    meio: "meio",
  };
  const out: PitchSectorMetric[] = [];
  for (const s of setores) {
    const id = idMap[s.setor.toLowerCase()];
    if (!id) continue;
    out.push({
      id,
      label: SECTOR_LABELS[id],
      colisao: s.colisao,
      attackDna: s.attackDna,
      permissividade: s.permissividade,
    });
  }
  return out;
}
