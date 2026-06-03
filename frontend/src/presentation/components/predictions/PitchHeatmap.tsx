import { useMemo, useState } from "react";
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

function heatColor(intensity: number, baseRgb: string): string {
  const alpha = 0.12 + intensity * 0.55;
  return `rgba(${baseRgb}, ${alpha})`;
}

export function PitchHeatmap({
  homeTeam,
  awayTeam,
  homeSectors,
  awaySectors,
  className = "",
}: PitchHeatmapProps) {
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

  const rgb =
    mode === "home"
      ? "0, 255, 136"
      : mode === "away"
        ? "168, 85, 247"
        : "0, 212, 255";

  const attackingTeam =
    mode === "home" ? homeTeam : mode === "away" ? awayTeam : null;

  const activeSector = activeId
    ? displaySectors.find((s) => s.id === activeId)
    : null;

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

      <div className="relative mx-auto max-w-md">
        <svg
          viewBox="0 0 100 150"
          className="w-full select-none"
          role="img"
          aria-label="Mapa de calor do gramado por setor"
        >
          <defs>
            <linearGradient id="pitchGrass" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#1a4d2e" />
              <stop offset="50%" stopColor="#1e5631" />
              <stop offset="100%" stopColor="#1a4d2e" />
            </linearGradient>
          </defs>

          <rect x="2" y="2" width="96" height="146" rx="2" fill="url(#pitchGrass)" />
          <rect
            x="2"
            y="2"
            width="96"
            height="146"
            rx="2"
            fill="none"
            stroke="rgba(255,255,255,0.35)"
            strokeWidth="0.6"
          />

          <line x1="2" y1="75" x2="98" y2="75" stroke="rgba(255,255,255,0.25)" strokeWidth="0.4" />
          <circle cx="50" cy="75" r="8" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.4" />
          <circle cx="50" cy="75" r="0.8" fill="rgba(255,255,255,0.3)" />

          <rect x="32" y="2" width="36" height="14" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.35" />
          <rect x="32" y="134" width="36" height="14" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.35" />

          {displaySectors.map((sector, i) => {
            const x = 2 + i * 32;
            const intensity = intensities[i];
            const isActive = activeId === sector.id;
            const duelSector = mode === "duel" ? (sector as DuelSectorMetric) : null;
            const net = duelSector?.net ?? 0;
            const fill =
              mode === "duel"
                ? net > 0.05
                  ? heatColor(intensity, "0, 255, 136")
                  : net < -0.05
                    ? heatColor(intensity, "168, 85, 247")
                    : heatColor(intensity * 0.3, "0, 212, 255")
                : heatColor(intensity, rgb);

            return (
              <g key={sector.id}>
                <motion.rect
                  x={x}
                  y="4"
                  width="30"
                  height="142"
                  fill={fill}
                  stroke={isActive ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.08)"}
                  strokeWidth={isActive ? 0.8 : 0.3}
                  className="cursor-pointer"
                  initial={false}
                  animate={{ opacity: isActive ? 1 : 0.85 }}
                  onMouseEnter={() => setActiveId(sector.id)}
                  onMouseLeave={() => setActiveId(null)}
                  onClick={() =>
                    setActiveId((prev) => (prev === sector.id ? null : sector.id))
                  }
                />
                <text
                  x={x + 15}
                  y="12"
                  textAnchor="middle"
                  fill="rgba(255,255,255,0.5)"
                  fontSize="3.2"
                  fontWeight="600"
                  pointerEvents="none"
                >
                  {SECTOR_LABELS[sector.id].toUpperCase()}
                </text>
              </g>
            );
          })}

          {attackingTeam && (
            <>
              <polygon
                points="50,138 46,148 54,148"
                fill={`rgba(${rgb}, 0.9)`}
              />
              <text x="50" y="153" textAnchor="middle" fill="white" fontSize="3.5" fontWeight="bold">
                {attackingTeam.slice(0, 12)}
              </text>
            </>
          )}
        </svg>

        <AnimatePresence>
          {activeSector && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              className="absolute bottom-2 left-2 right-2 rounded-xl border border-white/15 bg-surface/95 p-3 shadow-xl backdrop-blur-md"
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

      <p className="text-center text-[11px] text-slate-500">
        Passe o mouse ou toque em um setor · Verde = pressão {homeTeam} · Roxo = pressão{" "}
        {awayTeam}
      </p>
    </div>
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
      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
        active
          ? "border text-white"
          : "border border-white/10 bg-white/5 text-slate-400 hover:bg-white/10"
      }`}
      style={
        active && color
          ? { borderColor: `${color}60`, backgroundColor: `${color}18`, color }
          : active
            ? { borderColor: "rgba(0,212,255,0.5)", backgroundColor: "rgba(0,212,255,0.12)" }
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
      <p className="font-semibold text-white">Setor {sector.label}</p>
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
          <span className="font-mono font-semibold text-white">{sector.colisao.toFixed(2)}</span>
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
