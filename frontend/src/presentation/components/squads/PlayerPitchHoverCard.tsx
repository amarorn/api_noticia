import type { PlayerMatchStats } from "@/presentation/utils/playerMatchStats";

interface PlayerPitchHoverCardProps {
  playerName: string;
  club: string | null;
  squadPosition: string;
  matchStats?: PlayerMatchStats;
}

function lineLabel(line: string | null, position: string | null): string {
  if (position) return position;
  switch (line) {
    case "goleiro":
      return "Goleiro";
    case "defesa":
      return "Defesa";
    case "meio":
      return "Meio";
    case "ataque":
      return "Ataque";
    default:
      return "—";
  }
}

function ratingTone(rating: number): string {
  if (rating >= 7.4) return "text-neon-green";
  if (rating >= 6.8) return "text-amber-300";
  return "text-slate-300";
}

export function PlayerPitchHoverCard({
  playerName,
  club,
  squadPosition,
  matchStats,
}: PlayerPitchHoverCardProps) {
  const hasCards = (matchStats?.yellowCards ?? 0) > 0 || (matchStats?.redCards ?? 0) > 0;

  return (
    <div className="pointer-events-none w-48 rounded-xl border border-white/20 bg-gradient-to-br from-slate-950/90 via-emerald-950/75 to-neon-purple/20 p-2.5 shadow-[0_8px_32px_rgba(0,0,0,0.45)] backdrop-blur-md">
      <p className="text-sm font-bold text-white">{playerName}</p>
      <p className="mt-0.5 text-[11px] text-slate-400">
        {lineLabel(matchStats?.line ?? null, matchStats?.position ?? null)} · {squadPosition}
      </p>

      {matchStats ? (
        <div className="mt-2 space-y-1.5 text-xs">
          {!matchStats.isStarter ? (
            <p className="text-slate-400">Banco de reservas</p>
          ) : null}
          {matchStats.sofascoreRating != null ? (
            <div className="flex items-center justify-between gap-2">
              <span className="text-slate-500">Nota Sofascore</span>
              <span className={`font-mono font-bold ${ratingTone(matchStats.sofascoreRating)}`}>
                {matchStats.sofascoreRating.toFixed(2)}
              </span>
            </div>
          ) : (
            <p className="text-slate-500">Nota indisponível</p>
          )}

          <div className="flex items-center justify-between gap-2">
            <span className="text-slate-500">Cartões</span>
            <span className="font-medium text-white">
              {hasCards ? (
                <>
                  {matchStats.yellowCards > 0 ? (
                    <span className="text-amber-300">{matchStats.yellowCards} amarelo(s)</span>
                  ) : null}
                  {matchStats.yellowCards > 0 && matchStats.redCards > 0 ? " · " : null}
                  {matchStats.redCards > 0 ? (
                    <span className="text-red-400">{matchStats.redCards} vermelho(s)</span>
                  ) : null}
                </>
              ) : (
                <span className="text-slate-400">Nenhum</span>
              )}
            </span>
          </div>

          {matchStats.isCaptain ? (
            <p className="text-[11px] font-semibold text-neon-green">Capitão</p>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-xs text-slate-500">
          Passe o mouse após abrir um amistoso com escalação Sofascore
        </p>
      )}

      {club ? (
        <p className="mt-2 truncate text-[11px] text-slate-300">{club}</p>
      ) : matchStats && !matchStats.isStarter ? (
        <p className="mt-2 text-[11px] text-slate-500">Clube não informado na convocação</p>
      ) : null}
    </div>
  );
}
