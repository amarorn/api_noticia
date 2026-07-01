import { Link } from "react-router-dom";
import type { SuperbetLiveAdvice } from "@/domain/entities";

const POSSESSION_SOURCE_LABEL: Record<string, { label: string; className: string }> = {
  scorealarm: {
    label: "Posse ScoreAlarm",
    className: "bg-neon-green/15 text-neon-green border-neon-green/30",
  },
  sofascore: {
    label: "Posse Sofascore",
    className: "bg-neon-green/15 text-neon-green border-neon-green/30",
  },
  corners_proxy: {
    label: "Posse estimada (escanteios)",
    className: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  },
  momentum_proxy: {
    label: "Posse estimada (momentum)",
    className: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  },
  neutral: {
    label: "Posse neutra (50/50)",
    className: "bg-slate-500/15 text-slate-400 border-white/10",
  },
};

interface StatCellProps {
  label: string;
  home: number | string;
  away: number | string;
}

function StatCell({ label, home, away }: StatCellProps) {
  return (
    <div className="flex flex-col items-center gap-0.5 px-2 py-1">
      <span className="text-[9px] uppercase tracking-wider text-slate-600">{label}</span>
      <span className="font-mono text-sm font-bold text-white">
        <span className="text-neon-green">{home}</span>
        <span className="mx-1 text-slate-600">·</span>
        <span className="text-sky-300">{away}</span>
      </span>
    </div>
  );
}

interface LiveStatsCompactBarProps {
  data: SuperbetLiveAdvice;
  eventId: number;
}

/** Barra compacta de stats ao vivo + badge de fonte da posse. */
export function LiveStatsCompactBar({ data, eventId }: LiveStatsCompactBarProps) {
  const stats = data.liveStats;
  const sa = data.scorealarm?.stats ?? {};
  const homePoss = stats?.homePossessionPct ?? sa.home_possession_pct ?? null;
  const awayPoss =
    stats?.awayPossessionPct ??
    sa.away_possession_pct ??
    (homePoss != null ? Math.max(0, 100 - homePoss) : null);

  const homeShotsTotal = sa.home_shots ?? null;
  const awayShotsTotal = sa.away_shots ?? null;
  const homeShots = stats?.homeShotsOnTarget ?? sa.home_shots_on_target ?? null;
  const awayShots = stats?.awayShotsOnTarget ?? sa.away_shots_on_target ?? null;
  const homeCorners = stats?.homeCorners ?? sa.home_corners ?? 0;
  const awayCorners = stats?.awayCorners ?? sa.away_corners ?? 0;
  const homeYellow = stats?.homeYellowCards ?? sa.home_yellow_cards ?? 0;
  const awayYellow = stats?.awayYellowCards ?? sa.away_yellow_cards ?? 0;
  const homeFouls = sa.home_free_kicks ?? null;
  const awayFouls = sa.away_free_kicks ?? null;
  const homeXg = stats?.homeXg;
  const awayXg = stats?.awayXg;

  const possessionSource = stats?.possessionSource ?? "neutral";
  const sourceBadge =
    POSSESSION_SOURCE_LABEL[possessionSource] ?? POSSESSION_SOURCE_LABEL.neutral;

  const scoreParts = (data.currentScore ?? "0x0").split("x").map((n) => Number(n) || 0);
  const totalGoals = scoreParts[0] + scoreParts[1];
  const pressureHome =
    homePoss != null &&
    homePoss >= 65 &&
    (homeShotsTotal ?? homeShots ?? 0) >= 8 &&
    totalGoals === 0;
  const pressureAway =
    awayPoss != null &&
    awayPoss >= 65 &&
    (awayShotsTotal ?? awayShots ?? 0) >= 8 &&
    totalGoals === 0;

  const hasPossession = homePoss != null;
  const hasAnyStat =
    hasPossession ||
    homeShots != null ||
    homeShotsTotal != null ||
    homeCorners > 0 ||
    awayCorners > 0 ||
    homeYellow > 0 ||
    awayYellow > 0 ||
    homeXg != null ||
    homeFouls != null;

  return (
    <section className="glass-card p-3" aria-label="Estatísticas ao vivo">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Stats ao vivo
          </h2>
          <span
            className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${sourceBadge.className}`}
            title={stats?.warnings?.[0] ?? sourceBadge.label}
          >
            {sourceBadge.label}
          </span>
        </div>
        <Link
          to={`/ao-vivo/${eventId}`}
          className="text-[10px] font-medium text-neon-blue transition hover:text-sky-300"
        >
          Painel completo →
        </Link>
      </div>

      {data.scoreStale?.scoreStale && (
        <div className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[11px] text-red-200">
          <p className="font-semibold">Placar possivelmente desatualizado</p>
          <p className="mt-0.5 text-red-200/80">
            {data.scoreStale.warnings.join(" · ") ||
              "Superbet e timeline divergem — aguarde refresh completo."}
          </p>
        </div>
      )}

      {!hasAnyStat ? (
        <p className="text-xs text-slate-500">
          Escanteios e cartões no próximo refresh · xG/posse no modo completo (~60s)
        </p>
      ) : (
        <>
          {hasPossession && (
            <div className="mb-3">
              <div className="mb-1 flex justify-between text-[10px] text-slate-500">
                <span className="max-w-[40%] truncate">{data.homeTeam}</span>
                <span>Posse</span>
                <span className="max-w-[40%] truncate text-right">{data.awayTeam}</span>
              </div>
              <div className="flex h-2.5 overflow-hidden rounded-full bg-white/5">
                <div
                  className="h-full bg-neon-green/70 transition-all duration-700"
                  style={{ width: `${homePoss}%` }}
                />
                <div
                  className="h-full bg-sky-400/70 transition-all duration-700"
                  style={{ width: `${awayPoss ?? 0}%` }}
                />
              </div>
              <div className="mt-0.5 flex justify-between font-mono text-[10px] text-slate-400">
                <span>{homePoss.toFixed(0)}%</span>
                <span>{awayPoss?.toFixed(0) ?? "—"}%</span>
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-center divide-x divide-white/8 rounded-xl border border-white/8 bg-white/[0.02]">
            {homeXg != null && awayXg != null && (
              <StatCell
                label="xG"
                home={homeXg.toFixed(2)}
                away={awayXg.toFixed(2)}
              />
            )}
            {homeShotsTotal != null && awayShotsTotal != null && (
              <StatCell label="Finalizações" home={homeShotsTotal} away={awayShotsTotal} />
            )}
            {homeShots != null && awayShots != null && (
              <StatCell label="No alvo" home={homeShots} away={awayShots} />
            )}
            {(homeCorners > 0 || awayCorners > 0) && (
              <StatCell label="Escanteios" home={homeCorners} away={awayCorners} />
            )}
            {homeFouls != null && awayFouls != null && (
              <StatCell label="Faltas" home={homeFouls} away={awayFouls} />
            )}
            {(homeYellow > 0 || awayYellow > 0) && (
              <StatCell label="Amarelos" home={homeYellow} away={awayYellow} />
            )}
          </div>

          {(pressureHome || pressureAway) && (
            <p className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/10 px-2.5 py-2 text-[11px] text-amber-200">
              ⚠️ Pressão alta sem gol —{" "}
              {pressureHome ? data.homeTeam : data.awayTeam} domina posse e finalizações
            </p>
          )}

          {stats?.warnings?.[0] && (
            <p className="mt-2 text-[10px] text-amber-400/90">{stats.warnings[0]}</p>
          )}
        </>
      )}
    </section>
  );
}
