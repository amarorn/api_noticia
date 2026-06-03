/**
 * Página de figurinhas de jogadores de uma seleção.
 * Aberta ao clicar em uma seleção no Álbum 2026.
 */

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { IconArrowLeft, IconCheck } from "@/presentation/components/ui/Icons";
import {
  getRoster,
  POSITION_COLOR,
  POSITION_LABEL,
  type Player,
  type Position,
} from "@/data/albumPlayers";
import { TEAMS } from "@/presentation/pages/AlbumPage";

// ─── Retrato individual por jogador (nome exato do ROSTERS) ──────────────────
// Brasil: retratos gerados individualmente para cada jogador
// Demais times: fallback para o retrato genérico da seleção

const PLAYER_PORTRAIT: Record<string, string> = {
  // Brasil
  "Alisson":              "/images/player-brasil-1-alisson.png",
  "Ederson":              "/images/player-brasil-23-ederson.png",
  "Danilo":               "/images/player-brasil-2-danilo.png",
  "Marquinhos":           "/images/player-brasil-3-marquinhos.png",
  "Gabriel Magalhães":    "/images/player-brasil-4-gabriel.png",
  "Alex Telles":          "/images/player-brasil-12-telles.png",
  "Casemiro":             "/images/player-brasil-5-casemiro.png",
  "Fred":                 "/images/player-brasil-8-fred.png",
  "Lucas Paquetá":        "/images/player-brasil-10-paqueta.png",
  "Rodrygo":              "/images/player-brasil-7-rodrygo.png",
  "Raphinha":             "/images/player-brasil-11-raphinha.png",
  "Vinicius Jr":          "/images/player-brasil-20-vinicius.png",
  "Richarlison":          "/images/player-brasil-9-richarlison.png",
  "Endrick":              "/images/player-brasil-18-endrick.png",

  // Argentina
  "Emiliano Martínez":    "/images/player-arg-23-martinez.png",
  "Franco Armani":        "/images/player-arg-1-armani.png",
  "Cristian Romero":      "/images/player-arg-13-romero.png",
  "Nicolás Otamendi":     "/images/player-arg-4-otamendi.png",
  "Marcos Acuña":         "/images/player-arg-8-acuna.png",
  "Germán Pezzella":      "/images/player-arg-6-pezzella.png",
  "Rodrigo De Paul":      "/images/player-arg-7-depaul.png",
  "Enzo Fernández":       "/images/player-arg-24-enzo.png",
  "Lionel Messi":         "/images/player-arg-10-messi.png",
  "Lautaro Martínez":     "/images/player-arg-22-lautaro.png",
  "Julián Álvarez":       "/images/player-arg-9-alvarez.png",
  "Alexis Mac Allister":  "/images/player-arg-11-macallister.png",
  "Paulo Dybala":         "/images/player-arg-21-dybala.png",

  // França
  "Mike Maignan":         "/images/player-fra-16-maignan.png",
  "Hugo Lloris":          "/images/player-fra-1-lloris.png",
  "Theo Hernández":       "/images/player-fra-22-thernandez.png",
  "Jules Koundé":         "/images/player-fra-5-kounde.png",
  "Dayot Upamecano":      "/images/player-fra-4-upamecano.png",
  "N'Golo Kanté":         "/images/player-fra-13-kante.png",
  "Aurélien Tchouaméni":  "/images/player-fra-8-tchouameni.png",
  "Antoine Griezmann":    "/images/player-fra-6-griezmann.png",
  "Kylian Mbappé":        "/images/player-fra-10-mbappe.png",
  "Marcus Thuram":        "/images/player-fra-9-thuram.png",
  "Ousmane Dembélé":      "/images/player-fra-11-dembele.png",

  // Espanha
  "Unai Simón":           "/images/player-esp-1-simon.png",
  "Dani Carvajal":        "/images/player-esp-2-carvajal.png",
  "Robin Le Normand":     "/images/player-esp-24-lenormand.png",
  "Aymeric Laporte":      "/images/player-esp-5-laporte.png",
  "Nacho Fernández":      "/images/player-esp-4-nacho.png",
  "Rodri":                "/images/player-esp-16-rodri.png",
  "Pedri":                "/images/player-esp-8-pedri.png",
  "Gavi":                 "/images/player-esp-6-gavi.png",
  "Lamine Yamal":         "/images/player-esp-19-yamal.png",
  "Nico Williams":        "/images/player-esp-10-nwilliams.png",
  "Álvaro Morata":        "/images/player-esp-7-morata.png",
};

// ─── Retrato genérico por time (fallback quando não há retrato individual) ────

const TEAM_PORTRAIT: Record<string, string> = {
  "Brasil":         "/images/player-brasil.png",
  "Argentina":      "/images/player-argentina.png",
  "França":         "/images/player-franca.png",
  "Espanha":        "/images/player-espanha.png",
  "Alemanha":       "/images/player-alemanha.png",
  "Inglaterra":     "/images/player-brasil.png",
  "Portugal":       "/images/player-portugal.png",
  "Itália":         "/images/player-italia.png",
  "Holanda":        "/images/player-holanda.png",
  "Croácia":        "/images/player-croacia.png",
  "Marrocos":       "/images/player-marrocos.png",
  "Japão":          "/images/player-japao.png",
  "México":         "/images/player-mexico.png",
  "Senegal":        "/images/player-marrocos.png",
  "Colômbia":       "/images/player-mexico.png",
  "Uruguai":        "/images/player-argentina.png",
  "Bélgica":        "/images/player-franca.png",
  "Suécia":         "/images/player-alemanha.png",
  "Dinamarca":      "/images/player-alemanha.png",
  "Austrália":      "/images/player-brasil.png",
  "Suíça":          "/images/player-espanha.png",
  "Canadá":         "/images/player-brasil.png",
  "Estados Unidos": "/images/player-brasil.png",
};

function resolvePortrait(playerName: string, teamName: string): string {
  return (
    PLAYER_PORTRAIT[playerName] ??
    TEAM_PORTRAIT[teamName] ??
    "/images/player-brasil.png"
  );
}

// ─── Persistência separada dos jogadores coletados ────────────────────────────

const PLAYER_KEY = "wc2026_players_collected";

function loadPlayers(): Set<string> {
  try {
    const raw = localStorage.getItem(PLAYER_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

function savePlayers(set: Set<string>) {
  localStorage.setItem(PLAYER_KEY, JSON.stringify([...set]));
}

function playerKey(teamName: string, player: Player) {
  return `${teamName}::${player.number}::${player.name}`;
}

// ─── Figurinha do jogador ─────────────────────────────────────────────────────

function PlayerSticker({
  player,
  teamColor,
  teamName,
  index,
  collected,
  onToggle,
}: {
  player: Player;
  teamColor: string;
  teamName: string;
  index: number;
  collected: boolean;
  onToggle: () => void;
}) {
  const posColor = POSITION_COLOR[player.position];
  const portrait = resolvePortrait(player.name, teamName);

  return (
    <motion.button
      type="button"
      onClick={onToggle}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.03, 0.4), duration: 0.22 }}
      whileHover={{ scale: 1.05, y: -3 }}
      whileTap={{ scale: 0.96 }}
      className="group relative flex flex-col overflow-hidden rounded-xl text-left focus:outline-none"
      style={{
        border: `1.5px solid ${collected ? posColor : "rgba(255,255,255,0.09)"}`,
        filter: collected ? "none" : "saturate(0.3) brightness(0.55)",
        boxShadow: collected
          ? `0 0 22px ${posColor}40, 0 6px 20px rgba(0,0,0,0.6), inset 0 0 0 1px ${posColor}20`
          : "0 2px 8px rgba(0,0,0,0.4)",
        background: "#0a0f1a",
      }}
      aria-pressed={collected}
      aria-label={`${player.name} — ${collected ? "remover" : "coletar"}`}
    >
      {/* Foto / ilustração do jogador */}
      <div className="relative overflow-hidden" style={{ aspectRatio: "3/4" }}>
        <img
          src={portrait}
          alt={`Jogador — ${teamName}`}
          className="absolute inset-0 h-full w-full object-cover object-top"
          draggable={false}
          loading="lazy"
        />

        {/* Gradiente inferior para o nome */}
        <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/90 to-transparent" />

        {/* Número no canto superior esquerdo */}
        <div
          className="absolute left-1.5 top-1.5 flex h-6 w-6 items-center justify-center rounded-md text-[10px] font-black"
          style={{ backgroundColor: teamColor, color: "#0a0f1a" }}
        >
          {player.number}
        </div>

        {/* Badge posição canto superior direito */}
        <span
          className="absolute right-1.5 top-1.5 rounded-md px-1.5 py-0.5 text-[10px] font-black"
          style={{ backgroundColor: `${posColor}cc`, color: "#0a0f1a" }}
        >
          {player.position}
        </span>

        {/* Nome sobreposto na foto */}
        <div className="absolute inset-x-0 bottom-0 px-2 pb-1.5">
          <p className="truncate text-center text-[11px] font-black leading-tight text-white drop-shadow-lg">
            {player.name.split(" ").slice(-1)[0].toUpperCase()}
          </p>
        </div>

        {/* Checkmark overlay quando coletado */}
        <AnimatePresence>
          {collected && (
            <motion.div
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              className="absolute inset-0 z-20 flex items-end justify-end p-2"
            >
              <div
                className="flex h-7 w-7 items-center justify-center rounded-full shadow-lg"
                style={{ backgroundColor: posColor, color: "#0a0f1a" }}
              >
                <IconCheck className="h-4 w-4" />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Rodapé com info completa */}
      <div
        className="flex flex-col gap-0.5 px-2 py-1.5"
        style={{ background: `linear-gradient(135deg, ${teamColor}18, rgba(5,10,20,0.95))` }}
      >
        <p className="truncate text-center text-[11px] font-bold leading-tight text-white">
          {player.name}
        </p>
        <p className="truncate text-center text-[10px] text-slate-500">
          {player.club}
        </p>
        <p className="text-center text-[10px] font-semibold" style={{ color: posColor }}>
          {POSITION_LABEL[player.position]} · {player.born}
        </p>
      </div>
    </motion.button>
  );
}

// ─── Filtros de posição ──────────────────────────────────────────────────────

const POSITION_FILTERS: { value: Position | "ALL"; label: string }[] = [
  { value: "ALL", label: "Todos" },
  { value: "GK",  label: "Goleiros" },
  { value: "DEF", label: "Defesa" },
  { value: "MID", label: "Meio" },
  { value: "ATK", label: "Ataque" },
];

// ─── Página ───────────────────────────────────────────────────────────────────

export function TeamAlbumPage() {
  const { teamSlug } = useParams<{ teamSlug: string }>();
  const teamName = decodeURIComponent(teamSlug ?? "");

  const [collected, setCollected] = useState<Set<string>>(loadPlayers);
  const [posFilter, setPosFilter] = useState<Position | "ALL">("ALL");

  const roster = getRoster(teamName);
  const teamEntry = TEAMS.find((t) => t.name === teamName);
  const teamColor = teamEntry?.color ?? "#00ff88";

  const togglePlayer = (player: Player) => {
    const key = playerKey(teamName, player);
    setCollected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      savePlayers(next);
      return next;
    });
  };

  const players =
    posFilter === "ALL"
      ? (roster?.players ?? [])
      : (roster?.players ?? []).filter((p) => p.position === posFilter);

  const collectedCount = (roster?.players ?? []).filter((p) =>
    collected.has(playerKey(teamName, p)),
  ).length;
  const total = roster?.players.length ?? 0;

  return (
    <PageTransition className="space-y-6">
      {/* Breadcrumb */}
      <Link
        to="/album"
        className="inline-flex items-center gap-2 text-sm text-slate-400 transition-colors hover:text-white"
      >
        <IconArrowLeft className="h-4 w-4" />
        Voltar ao álbum
      </Link>

      {/* Header da seleção */}
      <div
        className="relative overflow-hidden rounded-2xl border"
        style={{ borderColor: `${teamColor}30`, minHeight: 120 }}
      >
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(ellipse at top left, ${teamColor}18 0%, transparent 60%),
                         radial-gradient(ellipse at bottom right, ${teamColor}10 0%, transparent 60%)`,
          }}
        />
        <div className="relative flex flex-wrap items-center gap-5 p-6">
          {/* Avatar grande */}
          <div
            className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl text-2xl font-black"
            style={{
              background: `${teamColor}18`,
              border: `2px solid ${teamColor}40`,
              color: teamColor,
              textShadow: `0 0 16px ${teamColor}60`,
            }}
          >
            {teamName.split(" ").filter((w) => w.length > 2).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || teamName.slice(0, 2).toUpperCase()}
          </div>

          <div className="flex-1">
            <h1 className="text-2xl font-black text-white">{teamName}</h1>
            <p className="mt-0.5 text-sm text-slate-400">
              Copa do Mundo 2026 · {collectedCount}/{total} figurinhas coletadas
            </p>
            {/* Barra de progresso */}
            <div className="mt-2 h-1.5 w-48 overflow-hidden rounded-full bg-white/[0.07]">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: teamColor }}
                initial={{ width: 0 }}
                animate={{ width: total > 0 ? `${(collectedCount / total) * 100}%` : "0%" }}
                transition={{ duration: 0.8, ease: "easeOut" }}
              />
            </div>
          </div>

          {/* Stats KXL do team */}
          {teamEntry && (
            <div className="flex gap-3">
              {[
                { label: "ATK", value: teamEntry.atk },
                { label: "DEF", value: teamEntry.def },
                { label: "CTL", value: teamEntry.ctrl },
              ].map(({ label, value }) => (
                <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2 text-center">
                  <p className="text-[10px] font-bold text-slate-500">{label}</p>
                  <p className="text-sm font-black text-white">{Math.round(value * 100)}</p>
                </div>
              ))}
              <div className="rounded-xl border border-white/[0.07] bg-white/[0.03] px-3 py-2 text-center">
                <p className="text-[10px] font-bold text-slate-500">POSSE</p>
                <p className="text-sm font-black text-white">{teamEntry.poss}%</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Sem roster */}
      {!roster && (
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] py-16 text-center text-slate-500">
          <p>Elenco detalhado em breve</p>
        </div>
      )}

      {/* Filtros de posição */}
      {roster && (
        <>
          <div className="flex flex-wrap gap-2">
            {POSITION_FILTERS.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                onClick={() => setPosFilter(value)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                  posFilter === value
                    ? "text-white"
                    : "border border-white/10 bg-white/[0.03] text-slate-500 hover:text-slate-300"
                }`}
                style={
                  posFilter === value && value !== "ALL"
                    ? {
                        borderWidth: 1,
                        borderStyle: "solid",
                        borderColor: `${POSITION_COLOR[value as Position]}50`,
                        backgroundColor: `${POSITION_COLOR[value as Position]}15`,
                        color: POSITION_COLOR[value as Position],
                      }
                    : posFilter === value
                      ? {
                          borderWidth: 1,
                          borderStyle: "solid",
                          borderColor: `${teamColor}50`,
                          backgroundColor: `${teamColor}15`,
                          color: teamColor,
                        }
                      : undefined
                }
              >
                {label}
              </button>
            ))}
          </div>

          {/* Grid de figurinhas */}
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7">
            {players.map((player, i) => (
              <PlayerSticker
                key={`${player.number}-${player.name}`}
                player={player}
                teamColor={teamColor}
                teamName={teamName}
                index={i}
                collected={collected.has(playerKey(teamName, player))}
                onToggle={() => togglePlayer(player)}
              />
            ))}
          </div>
        </>
      )}
    </PageTransition>
  );
}
