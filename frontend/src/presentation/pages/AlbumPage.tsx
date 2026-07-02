/**
 * Álbum digital Copa do Mundo 2026.
 * Dados de ataque/defesa/controle/posse vêm dos índices KXL calculados pelo backend
 * (mesmos valores usados no PossessionHeatmap e no modelo Dixon-Coles).
 * Estado "coletado" é persistido em localStorage.
 */

import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { IconSearch, IconCheck } from "@/presentation/components/ui/Icons";
import { TEAMS_WITH_ROSTER } from "@/data/albumPlayers";
import {
  REWARD_COPY,
  albumProgress,
  getRewardEvents,
} from "@/presentation/utils/albumRewards";

// ─── Dados reais dos 48 times — índices KXL do backend ────────────────────────

export interface TeamEntry {
  name: string;
  atk: number;
  def: number;
  ctrl: number;
  poss: number;
  /** Cor primária da seleção (hex) */
  color: string;
}

export const TEAMS: TeamEntry[] = [
  { name: "Argentina",                    atk: 0.843, def: 0.580, ctrl: 0.925, poss: 60, color: "#74b9e0" },
  { name: "Espanha",                       atk: 0.814, def: 0.512, ctrl: 0.920, poss: 63, color: "#c60b1e" },
  { name: "Brasil",                        atk: 0.824, def: 0.542, ctrl: 0.912, poss: 57, color: "#009c3b" },
  { name: "Portugal",                      atk: 0.776, def: 0.477, ctrl: 0.895, poss: 59, color: "#006600" },
  { name: "Inglaterra",                    atk: 0.753, def: 0.503, ctrl: 0.863, poss: 58, color: "#c8102e" },
  { name: "França",                        atk: 0.835, def: 0.499, ctrl: 0.849, poss: 54, color: "#003189" },
  { name: "Alemanha",                      atk: 0.783, def: 0.452, ctrl: 0.888, poss: 61, color: "#ffffff" },
  { name: "Cabo Verde",                    atk: 0.857, def: 0.393, ctrl: 0.780, poss: 47, color: "#003893" },
  { name: "Coreia do Sul",                 atk: 0.857, def: 0.393, ctrl: 0.780, poss: 47, color: "#c60c30" },
  { name: "Japão",                         atk: 0.857, def: 0.393, ctrl: 0.780, poss: 47, color: "#bc002d" },
  { name: "Bélgica",                       atk: 0.818, def: 0.343, ctrl: 0.820, poss: 52, color: "#ef3340" },
  { name: "Canadá",                        atk: 0.830, def: 0.402, ctrl: 0.787, poss: 49, color: "#ff0000" },
  { name: "Gana",                          atk: 0.830, def: 0.402, ctrl: 0.787, poss: 49, color: "#006b3f" },
  { name: "Suécia",                        atk: 0.791, def: 0.430, ctrl: 0.810, poss: 52, color: "#006aa7" },
  { name: "Áustria",                       atk: 0.792, def: 0.499, ctrl: 0.792, poss: 51, color: "#ed2939" },
  { name: "Panamá",                        atk: 0.803, def: 0.496, ctrl: 0.763, poss: 48, color: "#005293" },
  { name: "Uruguai",                       atk: 0.803, def: 0.496, ctrl: 0.763, poss: 48, color: "#75aadb" },
  { name: "Holanda",                       atk: 0.769, def: 0.464, ctrl: 0.804, poss: 53, color: "#ff6600" },
  { name: "Itália",                        atk: 0.727, def: 0.617, ctrl: 0.818, poss: 55, color: "#0066cc" },
  { name: "Costa do Marfim",               atk: 0.782, def: 0.467, ctrl: 0.815, poss: 52, color: "#f77f00" },
  { name: "Marrocos",                      atk: 0.762, def: 0.547, ctrl: 0.765, poss: 46, color: "#c1272d" },
  { name: "Arábia Saudita",               atk: 0.762, def: 0.547, ctrl: 0.765, poss: 46, color: "#006c35" },
  { name: "Argélia",                       atk: 0.762, def: 0.547, ctrl: 0.765, poss: 46, color: "#006233" },
  { name: "Uzbequistão",                   atk: 0.762, def: 0.547, ctrl: 0.765, poss: 46, color: "#1eb53a" },
  { name: "Senegal",                       atk: 0.758, def: 0.434, ctrl: 0.758, poss: 48, color: "#00853f" },
  { name: "Egito",                         atk: 0.776, def: 0.433, ctrl: 0.778, poss: 50, color: "#ce1126" },
  { name: "Colômbia",                      atk: 0.729, def: 0.434, ctrl: 0.791, poss: 50, color: "#fcd116" },
  { name: "Nova Zelândia",                 atk: 0.729, def: 0.434, ctrl: 0.791, poss: 50, color: "#00247d" },
  { name: "Curaçau",                       atk: 0.739, def: 0.396, ctrl: 0.773, poss: 50, color: "#003087" },
  { name: "México",                        atk: 0.739, def: 0.396, ctrl: 0.773, poss: 50, color: "#006847" },
  { name: "República Democrática do Congo",atk: 0.739, def: 0.396, ctrl: 0.773, poss: 50, color: "#007fff" },
  { name: "Estados Unidos",                atk: 0.766, def: 0.402, ctrl: 0.774, poss: 49, color: "#b22234" },
  { name: "África do Sul",                 atk: 0.766, def: 0.402, ctrl: 0.774, poss: 49, color: "#007a4d" },
  { name: "Austrália",                     atk: 0.768, def: 0.488, ctrl: 0.743, poss: 45, color: "#00843d" },
  { name: "Equador",                       atk: 0.768, def: 0.488, ctrl: 0.743, poss: 45, color: "#f5d300" },
  { name: "Jordânia",                      atk: 0.768, def: 0.488, ctrl: 0.743, poss: 45, color: "#007a3d" },
  { name: "Dinamarca",                     atk: 0.680, def: 0.464, ctrl: 0.766, poss: 51, color: "#c60c30" },
  { name: "Haiti",                         atk: 0.680, def: 0.464, ctrl: 0.766, poss: 51, color: "#00209f" },
  { name: "Irã",                           atk: 0.680, def: 0.464, ctrl: 0.766, poss: 51, color: "#239f40" },
  { name: "República Tcheca",              atk: 0.720, def: 0.499, ctrl: 0.784, poss: 51, color: "#d7141a" },
  { name: "Catar",                         atk: 0.692, def: 0.476, ctrl: 0.744, poss: 49, color: "#8d1b3d" },
  { name: "Suíça",                         atk: 0.692, def: 0.476, ctrl: 0.744, poss: 49, color: "#ff0000" },
  { name: "Tunísia",                       atk: 0.692, def: 0.476, ctrl: 0.744, poss: 49, color: "#e70013" },
  { name: "Croácia",                       atk: 0.711, def: 0.490, ctrl: 0.814, poss: 56, color: "#ff0000" },
  { name: "Iraque",                        atk: 0.711, def: 0.490, ctrl: 0.814, poss: 56, color: "#007a3d" },
  { name: "Bósnia",                        atk: 0.650, def: 0.428, ctrl: 0.654, poss: 43, color: "#003da5" },
  { name: "Escócia",                       atk: 0.622, def: 0.453, ctrl: 0.670, poss: 44, color: "#003087" },
  { name: "Paraguai",                      atk: 0.652, def: 0.491, ctrl: 0.653, poss: 42, color: "#d52b1e" },
];

// ─── Tier calculado a partir do attack_index ──────────────────────────────────

type Tier = "S" | "A" | "B" | "C";

function getTier(atk: number): Tier {
  if (atk >= 0.82) return "S";
  if (atk >= 0.77) return "A";
  if (atk >= 0.72) return "B";
  return "C";
}

const TIER_STYLE: Record<Tier, { border: string; bg: string; label: string; glow: string }> = {
  S: { border: "#fbbf24", bg: "rgba(251,191,36,0.08)", label: "text-yellow-400", glow: "rgba(251,191,36,0.25)" },
  A: { border: "#00d4ff", bg: "rgba(0,212,255,0.06)", label: "text-neon-blue", glow: "rgba(0,212,255,0.20)" },
  B: { border: "#00ff88", bg: "rgba(0,255,136,0.05)", label: "text-neon-green", glow: "rgba(0,255,136,0.15)" },
  C: { border: "#475569", bg: "rgba(71,85,105,0.10)", label: "text-slate-400", glow: "rgba(71,85,105,0.10)" },
};

const STORAGE_KEY = "wc2026_album_collected";

function loadCollected(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function saveCollected(set: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
}

// ─── Componente da figurinha ──────────────────────────────────────────────────

function Sticker({
  team,
  index,
  collected,
  onToggle,
}: {
  team: TeamEntry;
  index: number;
  collected: boolean;
  onToggle: () => void;
}) {
  const tier = getTier(team.atk);
  const style = TIER_STYLE[tier];
  const initials = team.name
    .split(" ")
    .filter((w) => w.length > 2)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase() || team.name.slice(0, 2).toUpperCase();

  return (
    <motion.button
      type="button"
      onClick={onToggle}
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: Math.min(index * 0.015, 0.4), duration: 0.25 }}
      whileHover={{ scale: 1.04, y: -2 }}
      whileTap={{ scale: 0.97 }}
      className="group relative flex flex-col overflow-hidden rounded-xl text-left transition-all focus:outline-none"
      style={{
        border: `1px solid ${collected ? style.border : "rgba(255,255,255,0.08)"}`,
        background: collected ? style.bg : "rgba(15,23,42,0.55)",
        boxShadow: collected ? `0 0 16px ${style.glow}` : "none",
        filter: collected ? "none" : "saturate(0.4) brightness(0.7)",
      }}
      aria-label={`${team.name} — ${collected ? "remover" : "coletar"}`}
      aria-pressed={collected}
    >
      {/* Número da figurinha */}
      <span
        className="absolute left-1.5 top-1.5 z-10 font-mono text-[10px] font-bold"
        style={{ color: collected ? style.border : "rgba(255,255,255,0.2)" }}
      >
        #{String(index + 1).padStart(2, "0")}
      </span>

      {/* Badge tier */}
      <span
        className={`absolute right-1.5 top-1.5 z-10 rounded px-1 py-px text-[10px] font-black ${style.label}`}
      >
        {tier}
      </span>

      {/* Check overlay quando coletado */}
      <AnimatePresence>
        {collected && (
          <motion.div
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            className="absolute inset-0 z-20 flex items-center justify-center"
            style={{ background: `${style.glow}` }}
          >
            <div
              className="flex h-7 w-7 items-center justify-center rounded-full"
              style={{ backgroundColor: style.border, color: "#0a0f1a" }}
            >
              <IconCheck className="h-4 w-4" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Avatar */}
      <div
        className="flex h-16 items-center justify-center"
        style={{
          background: `linear-gradient(135deg, ${team.color}22, ${team.color}08)`,
          borderBottom: `1px solid rgba(255,255,255,0.06)`,
        }}
      >
        <span
          className="text-2xl font-black tracking-tight"
          style={{ color: team.color, textShadow: `0 0 12px ${team.color}80` }}
        >
          {initials}
        </span>
      </div>

      {/* Info */}
      <div className="flex flex-col gap-1.5 p-2.5">
        <p className="truncate text-center text-[11px] font-semibold leading-tight text-white">
          {team.name}
        </p>

        {/* Barras de stats */}
        <div className="space-y-1">
          <StatBar label="ATK" value={team.atk} color="#00ff88" />
          <StatBar label="DEF" value={team.def} color="#00d4ff" />
          <StatBar label="CTL" value={team.ctrl} color="#a855f7" />
        </div>

        <p className="text-center font-mono text-[11px] text-slate-500">
          {team.poss}% posse
        </p>

        {/* Link para elenco quando disponível */}
        {TEAMS_WITH_ROSTER.has(team.name) && (
          <Link
            to={`/album/${encodeURIComponent(team.name)}`}
            onClick={(e) => e.stopPropagation()}
            className="mt-0.5 rounded-lg border border-white/[0.08] bg-white/[0.04] py-1 text-center text-[10px] font-semibold text-slate-500 transition hover:border-white/20 hover:text-white"
          >
            Ver elenco →
          </Link>
        )}
      </div>
    </motion.button>
  );
}

function StatBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-5 shrink-0 text-[10px] font-bold text-slate-500">{label}</span>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${value * 100}%`, backgroundColor: color, opacity: 0.75 }}
        />
      </div>
      <span className="w-5 shrink-0 text-right font-mono text-[10px] text-slate-500">
        {Math.round(value * 100)}
      </span>
    </div>
  );
}

// ─── Página principal ─────────────────────────────────────────────────────────

type FilterTab = "todos" | "coletados" | "faltando";

export function AlbumPage() {
  const [collected, setCollected] = useState<Set<string>>(loadCollected);
  const [filter, setFilter] = useState<FilterTab>("todos");
  const [search, setSearch] = useState("");

  const toggleCollected = (name: string) => {
    setCollected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      saveCollected(next);
      return next;
    });
  };

  const collectAll = () => {
    const all = new Set(TEAMS.map((t) => t.name));
    setCollected(all);
    saveCollected(all);
  };

  const clearAll = () => {
    const empty = new Set<string>();
    setCollected(empty);
    saveCollected(empty);
  };

  const filteredTeams = useMemo(() => {
    let list = TEAMS;
    if (search.trim()) {
      const q = search.toLowerCase().trim();
      list = list.filter((t) => t.name.toLowerCase().includes(q));
    }
    if (filter === "coletados") list = list.filter((t) => collected.has(t.name));
    if (filter === "faltando") list = list.filter((t) => !collected.has(t.name));
    return list;
  }, [filter, search, collected]);

  const pct = Math.round((collected.size / TEAMS.length) * 100);
  const rewardEvents = useMemo(() => getRewardEvents(), [collected.size]);
  const progress = albumProgress(collected, TEAMS.length);

  return (
    <PageTransition>
      {collected.size === 0 && (
        <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-4 text-sm text-amber-100/90">
          <p className="font-semibold text-amber-300">Nenhuma figurinha coletada ainda</p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-amber-100/80">
            <li>{REWARD_COPY.first_prediction}</li>
            <li>{REWARD_COPY.correct_result}</li>
            <li>{REWARD_COPY.round_complete}</li>
            <li>{REWARD_COPY.win_streak}</li>
          </ul>
          <p className="mt-2 text-xs text-slate-400">
            Você também pode clicar nas cartas para marcar manualmente ({progress.total} seleções).
          </p>
        </div>
      )}
      {/* Hero */}
      <div className="live-scoreboard glow-border relative overflow-hidden rounded-2xl border-yellow-500/25" style={{ minHeight: 160 }}>
        <img
          src="/images/album-hero.png"
          alt=""
          aria-hidden="true"
          className="absolute inset-0 h-full w-full object-cover object-center opacity-35"
          draggable={false}
        />
        <div className="absolute inset-0 bg-gradient-to-r from-surface/95 via-surface/75 to-surface/20" />
        <div className="relative flex flex-wrap items-end justify-between gap-4 p-6 sm:p-8">
          <div>
            <p className="text-xs font-bold uppercase tracking-widest text-yellow-500/70">
              Copa do Mundo
            </p>
            <h1 className="text-3xl font-black gradient-text sm:text-4xl">Álbum 2026</h1>
            <p className="mt-1 text-sm text-slate-400">
              {collected.size} de {TEAMS.length} figurinhas coletadas · Dados KXL reais
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <span className="text-3xl font-black" style={{ color: "#fbbf24" }}>
              {pct}%
            </span>
            <div className="h-2 w-40 overflow-hidden rounded-full bg-white/[0.07]">
              <motion.div
                className="h-full rounded-full"
                style={{ background: "linear-gradient(90deg, #fbbf24, #f59e0b)" }}
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 1, ease: "easeOut" }}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={collectAll}
                className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-2.5 py-1 text-[10px] font-semibold text-yellow-400 transition hover:bg-yellow-500/20"
              >
                Completar álbum
              </button>
              <button
                type="button"
                onClick={clearAll}
                className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] font-semibold text-slate-500 transition hover:bg-white/10"
              >
                Limpar
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Tier legend */}
      <div className="flex flex-wrap gap-3">
        {(["S", "A", "B", "C"] as Tier[]).map((tier) => {
          const s = TIER_STYLE[tier];
          const count = TEAMS.filter((t) => getTier(t.atk) === tier).length;
          return (
            <div key={tier} className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-1.5">
              <span className={`text-xs font-black ${s.label}`}>{tier}</span>
              <span className="text-xs text-slate-500">{count} times</span>
              <div className="h-1.5 w-12 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full" style={{ width: "100%", backgroundColor: s.border, opacity: 0.6 }} />
              </div>
            </div>
          );
        })}
        <div className="ml-auto flex items-center gap-1.5 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-1.5 text-xs text-slate-500">
          Clique na figurinha para coletar
        </div>
      </div>

      {rewardEvents.length > 0 && (
        <div className="rounded-xl border border-neon-green/20 bg-neon-green/5 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-neon-green">
            Recompensas recentes
          </p>
          <ul className="mt-2 space-y-1 text-xs text-slate-300">
            {rewardEvents.slice(0, 5).map((event) => (
              <li key={event.id}>
                {event.label}
                {event.team ? ` · ${event.team}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Filtros + busca */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-xl border border-white/[0.07] bg-white/[0.03] p-1">
          {(["todos", "coletados", "faltando"] as FilterTab[]).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setFilter(tab)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium capitalize transition-all ${
                filter === tab
                  ? "bg-neon-green/15 text-neon-green"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {tab}
              {tab === "coletados" && collected.size > 0 && (
                <span className="ml-1.5 rounded-full bg-neon-green/20 px-1.5 py-0.5 text-[10px] text-neon-green">
                  {collected.size}
                </span>
              )}
              {tab === "faltando" && TEAMS.length - collected.size > 0 && (
                <span className="ml-1.5 rounded-full bg-white/10 px-1.5 py-0.5 text-[10px] text-slate-400">
                  {TEAMS.length - collected.size}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="relative flex-1 sm:max-w-xs">
          <IconSearch className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar seleção..."
            className="input-field pl-8 text-xs"
          />
        </div>
      </div>

      {/* Grid de figurinhas */}
      <AnimatePresence mode="wait">
        {filteredTeams.length === 0 ? (
          <motion.div
            key="empty"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="py-16 text-center text-slate-500"
          >
            Nenhuma figurinha encontrada
          </motion.div>
        ) : (
          <motion.div
            key="grid"
            className="grid grid-cols-3 gap-2.5 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8"
          >
            {filteredTeams.map((team, i) => (
              <Sticker
                key={team.name}
                team={team}
                index={i}
                collected={collected.has(team.name)}
                onToggle={() => toggleCollected(team.name)}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </PageTransition>
  );
}
