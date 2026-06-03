import { useState } from "react";
import { motion } from "framer-motion";
import type { KxlLethalityBreakdown } from "@/domain/entities";
import { outcomeColors } from "@/presentation/theme";

interface LethalityGkPanelProps {
  homeTeam: string;
  awayTeam: string;
  home: KxlLethalityBreakdown;
  away: KxlLethalityBreakdown;
  note?: string;
}

const METHOD_ICONS: Record<string, string> = {
  "cabeça": "C",
  "fora da área": "F",
  "dentro da área": "A",
  "bola parada": "BP",
};

export function LethalityGkPanel({
  homeTeam,
  awayTeam,
  home,
  away,
  note,
}: LethalityGkPanelProps) {
  const [side, setSide] = useState<"home" | "away">("home");
  const active = side === "home" ? home : away;
  const team = side === "home" ? homeTeam : awayTeam;
  const color = side === "home" ? outcomeColors["1"] : outcomeColors["2"];
  const maxP = Math.max(...active.metodos.map((m) => m.pressao), 0.01);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-white">Letalidade × Goleiro</h4>
          <p className="mt-0.5 text-xs text-slate-500">
            Ataque (%) contra fraqueza do GK adversário por tipo de finalização
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-white/10 bg-black/20 p-0.5">
          <SideTab active={side === "home"} label={homeTeam} color={outcomeColors["1"]} onClick={() => setSide("home")} />
          <SideTab active={side === "away"} label={awayTeam} color={outcomeColors["2"]} onClick={() => setSide("away")} />
        </div>
      </div>

      {note && (
        <p
          className="mt-3 rounded-lg border px-3 py-2 text-xs"
          style={{ borderColor: `${color}35`, backgroundColor: `${color}10`, color }}
        >
          {note}
        </p>
      )}

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {active.metodos.map((m) => {
          const isDom = m.metodo === active.dominant;
          const pct = (m.pressao / maxP) * 100;
          return (
            <motion.div
              key={m.metodo}
              layout
              className={`rounded-xl border p-3 transition-colors ${
                isDom ? "border-white/20 bg-white/[0.06]" : "border-white/5 bg-white/[0.02]"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold"
                    style={{ backgroundColor: `${color}20`, color }}
                  >
                    {METHOD_ICONS[m.metodo] ?? "?"}
                  </span>
                  <div>
                    <p className="text-xs font-medium capitalize text-white">{m.metodo}</p>
                    {isDom && (
                      <p className="text-[10px] text-slate-500">via dominante</p>
                    )}
                  </div>
                </div>
                <span className="font-mono text-sm font-bold text-white">
                  {m.pressao.toFixed(2)}
                </span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  className="h-full rounded-full"
                  style={{ backgroundColor: color }}
                />
              </div>
              <div className="mt-2 flex justify-between text-[10px] text-slate-500">
                <span>Ataque {m.ataquePct}%</span>
                <span>GK fraco {m.gkFracoPct}%</span>
              </div>
            </motion.div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-400">
        <span>
          Índice {team}: <strong className="text-white">{active.index.toFixed(2)}</strong>
        </span>
        <span>
          Chances perdidas/jogo: <strong className="text-white">{active.eacp.toFixed(1)}</strong>
        </span>
      </div>
    </div>
  );
}

function SideTab({
  active,
  label,
  color,
  onClick,
}: {
  active: boolean;
  label: string;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`max-w-[120px] truncate rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
        active ? "text-white" : "text-slate-500 hover:text-slate-300"
      }`}
      style={active ? { backgroundColor: `${color}25`, color } : undefined}
    >
      {label}
    </button>
  );
}
