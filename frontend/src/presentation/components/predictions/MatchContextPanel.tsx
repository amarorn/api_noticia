import type { ReactNode } from "react";
import { motion } from "framer-motion";
import type { KxlCollisionBreakdown, WcPrediction } from "@/domain/entities";
import { formatPercent, outcomeColors } from "@/presentation/theme";
import { LethalityGkPanel } from "@/presentation/components/predictions/LethalityGkPanel";
import { PitchHeatmap, sectorsFromCollision } from "@/presentation/components/predictions/PitchHeatmap";
import { buildMatchContextView } from "@/presentation/utils/parseMatchContext";

interface MatchContextPanelProps {
  prediction: WcPrediction;
}

export function MatchContextPanel({ prediction }: MatchContextPanelProps) {
  const view = buildMatchContextView(prediction);
  const collision = prediction.modelBreakdown.kxlCollision;

  return (
    <div className="space-y-6">
      {view.preMatch && (
        <ContextSection
          title="Estatísticas pré-jogo"
          subtitle="Copa do Mundo · histórico e forma"
          accent="#00d4ff"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <TeamPreMatchCard
              team={prediction.homeTeam}
              stats={view.preMatch.home}
              side="home"
            />
            <TeamPreMatchCard
              team={prediction.awayTeam}
              stats={view.preMatch.away}
              side="away"
            />
          </div>
          <H2HStrip
            homeTeam={prediction.homeTeam}
            awayTeam={prediction.awayTeam}
            h2h={view.preMatch.h2h}
          />
        </ContextSection>
      )}

      {view.kxlProfile && (
        <ContextSection
          title="Perfil tático KXL"
          subtitle="Baseline Copa 2026 · DNA da seleção"
          accent="#a855f7"
        >
          {view.kxlProfile.sectorNote && (
            <p className="mb-4 rounded-xl border border-neon-purple/25 bg-neon-purple/10 px-4 py-2.5 text-sm text-neon-purple">
              {view.kxlProfile.sectorNote}
            </p>
          )}
          <div className="grid gap-6 lg:grid-cols-2">
            <KxlProfileCard
              team={prediction.homeTeam}
              profile={view.kxlProfile.home}
              color={outcomeColors["1"]}
            />
            <KxlProfileCard
              team={prediction.awayTeam}
              profile={view.kxlProfile.away}
              color={outcomeColors["2"]}
            />
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <PressureCompare
              homeTeam={prediction.homeTeam}
              awayTeam={prediction.awayTeam}
              home={view.kxlProfile.pressureHome}
              away={view.kxlProfile.pressureAway}
            />
            <VectorProbStrip
              label="Palpite vetorial (KXL)"
              probHome={view.kxlProfile.probHome}
              probDraw={view.kxlProfile.probDraw}
              probAway={view.kxlProfile.probAway}
            />
          </div>
        </ContextSection>
      )}

      {collision && (
        <ContextSection
          title="Colisão KXL"
          subtitle="Vcar × Vesc · Energia, Espaço e Tempo"
          accent="#00ff88"
        >
          <PitchHeatmap
            homeTeam={prediction.homeTeam}
            awayTeam={prediction.awayTeam}
            homeSectors={sectorsFromCollision(collision.home.setores)}
            awaySectors={sectorsFromCollision(collision.away.setores)}
            className="mb-6"
          />
          {collision.home.lethalityGk && collision.away.lethalityGk && (
            <LethalityGkPanel
              homeTeam={prediction.homeTeam}
              awayTeam={prediction.awayTeam}
              home={collision.home.lethalityGk}
              away={collision.away.lethalityGk}
              note={collision.lethalityNote}
            />
          )}
          <CollisionDuel
            homeTeam={prediction.homeTeam}
            awayTeam={prediction.awayTeam}
            collision={collision}
          />
        </ContextSection>
      )}
    </div>
  );
}

function ContextSection({
  title,
  subtitle,
  accent,
  children,
}: {
  title: string;
  subtitle: string;
  accent: string;
  children: ReactNode;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.04] to-transparent"
    >
      <div
        className="border-b border-white/5 px-5 py-4"
        style={{ borderLeftWidth: 3, borderLeftColor: accent }}
      >
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="text-xs text-slate-500">{subtitle}</p>
      </div>
      <div className="p-5">{children}</div>
    </motion.section>
  );
}

function TeamPreMatchCard({
  team,
  stats,
  side,
}: {
  team: string;
  stats: { elo: number; goalsPerGame: number; concededPerGame: number; form: string };
  side: "home" | "away";
}) {
  const accent = side === "home" ? outcomeColors["1"] : outcomeColors["2"];
  const maxElo = 1700;
  const eloPct = Math.min(100, (stats.elo / maxElo) * 100);

  return (
    <div
      className="rounded-xl border p-4"
      style={{ borderColor: `${accent}30`, backgroundColor: `${accent}08` }}
    >
      <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
        {side === "home" ? "Mandante" : "Visitante"}
      </p>
      <p className="mt-1 text-xl font-bold text-white">{team}</p>
      <div className="mt-4 space-y-3">
        <StatRow label="Elo" value={stats.elo.toFixed(0)} pct={eloPct} color={accent} />
        <StatRow
          label="Gols / jogo"
          value={stats.goalsPerGame.toFixed(2)}
          pct={Math.min(100, stats.goalsPerGame * 50)}
          color={accent}
        />
        <StatRow
          label="Sofridos / jogo"
          value={stats.concededPerGame.toFixed(2)}
          pct={Math.min(100, stats.concededPerGame * 50)}
          color="#f59e0b"
          invert
        />
      </div>
      <div className="mt-4 flex flex-wrap gap-1">
        {stats.form.split("-").map((f, i) => (
          <FormChip key={`${f}-${i}`} result={f} />
        ))}
      </div>
    </div>
  );
}

function FormChip({ result }: { result: string }) {
  const map: Record<string, string> = {
    V: "bg-neon-green/20 text-neon-green",
    E: "bg-neon-blue/20 text-neon-blue",
    D: "bg-red-400/20 text-red-300",
  };
  const label = { V: "V", E: "E", D: "D" }[result] ?? result;
  return (
    <span
      className={`inline-flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold ${map[result] ?? "bg-white/10 text-slate-400"}`}
    >
      {label}
    </span>
  );
}

function StatRow({
  label,
  value,
  pct,
  color,
  invert,
}: {
  label: string;
  value: string;
  pct: number;
  color: string;
  invert?: boolean;
}) {
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-slate-500">{label}</span>
        <span className="font-semibold text-white">{value}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/10">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{
            backgroundColor: color,
            opacity: invert ? 0.7 : 1,
          }}
        />
      </div>
    </div>
  );
}

function H2HStrip({
  homeTeam,
  awayTeam,
  h2h,
}: {
  homeTeam: string;
  awayTeam: string;
  h2h: { homeWins: number; draws: number; awayWins: number; total: number };
}) {
  if (h2h.total === 0) {
    return (
      <p className="mt-4 text-center text-sm text-slate-500">
        Sem confrontos diretos registrados em Copas do Mundo
      </p>
    );
  }
  const total = h2h.total || 1;
  return (
    <div className="mt-5 rounded-xl bg-white/[0.03] p-4">
      <p className="mb-3 text-center text-xs uppercase tracking-wider text-slate-500">
        Confronto direto em Copas ({h2h.total} jogos)
      </p>
      <div className="flex h-3 overflow-hidden rounded-full">
        <div
          className="bg-neon-green/80 transition-all"
          style={{ width: `${(h2h.homeWins / total) * 100}%` }}
          title={`${homeTeam}: ${h2h.homeWins}`}
        />
        <div
          className="bg-neon-blue/80"
          style={{ width: `${(h2h.draws / total) * 100}%` }}
        />
        <div
          className="bg-neon-purple/80"
          style={{ width: `${(h2h.awayWins / total) * 100}%` }}
          title={`${awayTeam}: ${h2h.awayWins}`}
        />
      </div>
      <div className="mt-2 flex justify-between text-xs text-slate-400">
        <span>
          {homeTeam} <strong className="text-neon-green">{h2h.homeWins}</strong>
        </span>
        <span>
          Empates <strong className="text-neon-blue">{h2h.draws}</strong>
        </span>
        <span>
          <strong className="text-neon-purple">{h2h.awayWins}</strong> {awayTeam}
        </span>
      </div>
    </div>
  );
}

function KxlProfileCard({
  team,
  profile,
  color,
}: {
  team: string;
  profile: {
    attack: number;
    defense: number;
    control: number;
    shots?: number;
    possession?: number;
    counter?: number;
    gkWeakness?: number;
  };
  color: string;
}) {
  const metrics = [
    { key: "Ataque", value: profile.attack, max: 1.2 },
    { key: "Defesa", value: profile.defense, max: 1.2 },
    { key: "Controle", value: profile.control, max: 1.2 },
  ];

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4">
      <p className="font-bold text-white">{team}</p>
      <div className="mt-4 space-y-2.5">
        {metrics.map((m) => (
          <StatRow
            key={m.key}
            label={m.key}
            value={m.value.toFixed(2)}
            pct={(m.value / m.max) * 100}
            color={color}
          />
        ))}
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        {profile.shots != null && (
          <MiniStat label="Chutes/jogo" value={profile.shots.toFixed(1)} />
        )}
        {profile.possession != null && (
          <MiniStat label="Posse" value={`${Math.round(profile.possession * 100)}%`} />
        )}
        {profile.counter != null && (
          <MiniStat label="Contra-ataque" value={profile.counter.toFixed(1)} />
        )}
        {profile.gkWeakness != null && (
          <MiniStat label="GK área fraca" value={`${Math.round(profile.gkWeakness * 100)}%`} />
        )}
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/5 px-2.5 py-2">
      <p className="text-[10px] text-slate-500">{label}</p>
      <p className="font-semibold text-slate-200">{value}</p>
    </div>
  );
}

function PressureCompare({
  homeTeam,
  awayTeam,
  home,
  away,
}: {
  homeTeam: string;
  awayTeam: string;
  home: number;
  away: number;
}) {
  const max = Math.max(home, away, 0.01);
  return (
    <div className="rounded-xl bg-white/[0.03] p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">
        Pressão ofensiva
      </p>
      <div className="mt-3 space-y-2">
        <VersusBar label={homeTeam} value={home} max={max} color={outcomeColors["1"]} />
        <VersusBar label={awayTeam} value={away} max={max} color={outcomeColors["2"]} />
      </div>
    </div>
  );
}

function VersusBar({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
}) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="truncate text-slate-400">{label}</span>
        <span className="font-mono text-white">{value.toFixed(2)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/10">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${(value / max) * 100}%` }}
          className="h-full rounded-full"
          style={{ backgroundColor: color }}
        />
      </div>
    </div>
  );
}

function VectorProbStrip({
  label,
  probHome,
  probDraw,
  probAway,
}: {
  label: string;
  probHome: number;
  probDraw: number;
  probAway: number;
}) {
  return (
    <div className="rounded-xl bg-white/[0.03] p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <div className="mt-3 flex gap-2">
        <ProbChip outcome="1" value={probHome} color={outcomeColors["1"]} />
        <ProbChip outcome="X" value={probDraw} color={outcomeColors["X"]} />
        <ProbChip outcome="2" value={probAway} color={outcomeColors["2"]} />
      </div>
    </div>
  );
}

function ProbChip({
  outcome,
  value,
  color,
}: {
  outcome: string;
  value: number;
  color: string;
}) {
  return (
    <div
      className="flex flex-1 flex-col items-center rounded-xl border py-2"
      style={{ borderColor: `${color}40`, backgroundColor: `${color}12` }}
    >
      <span className="text-lg font-bold" style={{ color }}>
        {outcome}
      </span>
      <span className="text-xs text-slate-400">{formatPercent(value, 0)}</span>
    </div>
  );
}

function CollisionDuel({
  homeTeam,
  awayTeam,
  collision,
}: {
  homeTeam: string;
  awayTeam: string;
  collision: KxlCollisionBreakdown;
}) {
  const maxV = Math.max(
    collision.home.vEff,
    collision.away.vEff,
    0.01,
  );
  const leader =
    collision.vDelta > 0.02
      ? homeTeam
      : collision.vDelta < -0.02
        ? awayTeam
        : null;

  return (
    <div className="space-y-5">
      {collision.sectorNote && (
        <p className="rounded-xl border border-neon-green/20 bg-neon-green/10 px-4 py-2 text-sm text-neon-green">
          {collision.sectorNote}
        </p>
      )}

      <div className="relative rounded-2xl border border-white/10 bg-black/20 p-6">
        <div className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/20 bg-surface px-3 py-1 text-xs font-bold text-slate-400">
          V_eff
        </div>
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <div className="text-right">
            <p className="text-sm font-bold text-white">{homeTeam}</p>
            <p className="font-mono text-2xl font-bold text-neon-green">
              {collision.home.vEff.toFixed(3)}
            </p>
            <p className="text-[10px] text-slate-500">
              Vcar {collision.home.vcarRaw.toFixed(2)} · Vesc {collision.home.vesc.toFixed(2)}
            </p>
          </div>
          <div className="flex flex-col items-center gap-1 px-2">
            <span
              className={`text-xs font-medium ${collision.vDelta >= 0 ? "text-neon-green" : "text-neon-purple"}`}
            >
              Δ {collision.vDelta >= 0 ? "+" : ""}
              {collision.vDelta.toFixed(3)}
            </span>
          </div>
          <div>
            <p className="text-sm font-bold text-white">{awayTeam}</p>
            <p className="font-mono text-2xl font-bold text-neon-purple">
              {collision.away.vEff.toFixed(3)}
            </p>
            <p className="text-[10px] text-slate-500">
              Vcar {collision.away.vcarRaw.toFixed(2)} · Vesc {collision.away.vesc.toFixed(2)}
            </p>
          </div>
        </div>
        <div className="mt-6 flex h-4 overflow-hidden rounded-full">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${(collision.home.vEff / maxV) * 50}%` }}
            className="bg-gradient-to-r from-neon-green/80 to-neon-green/40"
          />
          <div className="w-1 bg-white/20" />
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${(collision.away.vEff / maxV) * 50}%` }}
            className="ml-auto bg-gradient-to-l from-neon-purple/80 to-neon-purple/40"
          />
        </div>
        {leader && (
          <p className="mt-3 text-center text-xs text-slate-400">
            Leve vantagem de colisão para <span className="text-white">{leader}</span>
          </p>
        )}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <PillarCard
          team={homeTeam}
          energia={collision.home.energia}
          espaco={collision.home.espaco}
          tempo={collision.home.tempo}
          setores={collision.home.setores}
          color={outcomeColors["1"]}
        />
        <PillarCard
          team={awayTeam}
          energia={collision.away.energia}
          espaco={collision.away.espaco}
          tempo={collision.away.tempo}
          setores={collision.away.setores}
          color={outcomeColors["2"]}
        />
      </div>

      <VectorProbStrip
        label="Resultado da colisão"
        probHome={collision.probHome}
        probDraw={collision.probDraw}
        probAway={collision.probAway}
      />
    </div>
  );
}

function PillarCard({
  team,
  energia,
  espaco,
  tempo,
  setores,
  color,
}: {
  team: string;
  energia: number;
  espaco: number;
  tempo: number;
  setores: { setor: string; colisao: number }[];
  color: string;
}) {
  const pillars = [
    { label: "Energia", value: energia, max: 1.3 },
    { label: "Espaço", value: espaco, max: 2 },
    { label: "Tempo (TBRTL)", value: tempo, max: 1.15 },
  ];
  const topSector = [...setores].sort((a, b) => b.colisao - a.colisao)[0];

  return (
    <div className="rounded-xl border border-white/10 p-4">
      <p className="text-sm font-semibold text-white">{team}</p>
      <div className="mt-3 space-y-2">
        {pillars.map((p) => (
          <StatRow
            key={p.label}
            label={p.label}
            value={p.value.toFixed(2)}
            pct={(p.value / p.max) * 100}
            color={color}
          />
        ))}
      </div>
      {topSector && (
        <p className="mt-3 text-xs text-slate-500">
          Setor mais forte:{" "}
          <span className="font-medium text-slate-300">
            {topSector.setor} ({topSector.colisao.toFixed(2)})
          </span>
        </p>
      )}
    </div>
  );
}
