import { useState } from "react";
import type { RefereeMarkets, RefereeProfile } from "@/domain/entities";
import { IconChevronRight } from "@/presentation/components/ui/Icons";

interface LiveRefereePanelProps {
  refereeMarkets: RefereeMarkets | null | undefined;
  refereeProfile: RefereeProfile | null | undefined;
  currentMinute: number;
  homeYellows?: number;
  awayYellows?: number;
  homeReds?: number;
  awayReds?: number;
  compact?: boolean;
}

const classificationColors: Record<string, string> = {
  punitivista: "text-rose-400 border-rose-700/40 bg-rose-900/20",
  equilibrado: "text-amber-400 border-amber-700/40 bg-amber-900/20",
  pacificador: "text-emerald-400 border-emerald-700/40 bg-emerald-900/20",
};

const classificationLabels: Record<string, string> = {
  punitivista: "Punitivista 🟨🟨",
  equilibrado: "Equilibrado ⚖️",
  pacificador: "Pacificador 🕊️",
};

function RefereeBadge({ profile }: { profile: RefereeProfile }) {
  const cls = profile.classification;
  const colorClass = classificationColors[cls] || classificationColors.equilibrado;
  const label = classificationLabels[cls] || profile.classificationPt;

  return (
    <div className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-semibold ${colorClass}`}>
      <span className="truncate">{profile.name}</span>
      <span className="opacity-70">|</span>
      <span>{label}</span>
      <span className="opacity-70">λ={profile.cardLambda.toFixed(1)}</span>
    </div>
  );
}

function MarketLineRow({ line }: { line: NonNullable<RefereeMarkets["yellowCards"]["overLines"][0]> }) {
  const isOver = line.recommendation === "over";
  const isUnder = line.recommendation === "under";
  const recColor = isOver ? "text-emerald-400" : isUnder ? "text-rose-400" : "text-neutral-400";
  const confColor = line.confidence === "alta" ? "text-emerald-400" : line.confidence === "media" ? "text-amber-400" : "text-neutral-400";

  return (
    <div className="flex items-center justify-between py-1.5 text-xs border-b border-white/5 last:border-0">
      <span className="text-neutral-300">Over {line.line}</span>
      <div className="flex items-center gap-3">
        <span className="text-neutral-400">{(line.overProb * 100).toFixed(0)}%</span>
        <span className="text-neutral-500">Fair @{line.overOddsFair.toFixed(2)}</span>
        <span className={`font-semibold ${recColor}`}>{line.recommendation.toUpperCase()}</span>
        <span className={`text-[10px] uppercase ${confColor}`}>{line.confidence}</span>
      </div>
    </div>
  );
}

function YesNoBadge({
  label,
  prob,
  oddsFair,
  recommendation,
}: {
  label: string;
  prob: number;
  oddsFair: number;
  recommendation: string;
  confidence: string;
}) {
  const isYes = recommendation === "sim";
  const recColor = isYes ? "text-emerald-400" : "text-neutral-400";

  return (
    <div className="flex items-center justify-between py-1.5 text-xs">
      <span className="text-neutral-300">{label}</span>
      <div className="flex items-center gap-3">
        <span className="text-neutral-400">{(prob * 100).toFixed(0)}%</span>
        <span className="text-neutral-500">Fair @{oddsFair.toFixed(2)}</span>
        <span className={`font-semibold ${recColor}`}>{recommendation.toUpperCase()}</span>
      </div>
    </div>
  );
}

export default function LiveRefereePanel({
  refereeMarkets,
  refereeProfile,
  currentMinute,
  homeYellows = 0,
  awayYellows = 0,
  homeReds = 0,
  awayReds = 0,
  compact = false,
}: LiveRefereePanelProps) {
  const [expanded, setExpanded] = useState(!compact);

  if (!refereeMarkets && !refereeProfile) {
    return (
      <div className="rounded-xl border border-white/10 bg-neutral-900/50 p-3">
        <div className="text-xs text-neutral-500 text-center">Dados do árbitro não disponíveis</div>
      </div>
    );
  }

  const yellows = refereeMarkets?.yellowCards;
  const reds = refereeMarkets?.redCards;
  const penalties = refereeMarkets?.penalties;
  const fouls = refereeMarkets?.fouls;
  const totalYellows = homeYellows + awayYellows;
  const totalReds = homeReds + awayReds;

  return (
    <div className="rounded-xl border border-white/10 bg-neutral-900/50 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">🟨 Árbitro & Cartões</span>
          {refereeProfile && <RefereeBadge profile={refereeProfile} />}
        </div>
        {expanded ? (
          <IconChevronRight className="w-4 h-4 text-neutral-400 rotate-90" />
        ) : (
          <IconChevronRight className="w-4 h-4 text-neutral-400 -rotate-90" />
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-3">
          {/* Current state */}
          <div className="flex items-center gap-3 text-xs">
            <div className="flex items-center gap-1">
              <span className="text-yellow-500">🟨</span>
              <span className="text-neutral-300">{totalYellows} amarelos</span>
              {yellows && (
                <span className="text-neutral-500">
                  (esperado FT: {yellows.expectedTotal.toFixed(1)})
                </span>
              )}
            </div>
            {totalReds > 0 && (
              <div className="flex items-center gap-1">
                <span className="text-red-500">🟥</span>
                <span className="text-neutral-300">{totalReds} vermelhos</span>
              </div>
            )}
          </div>

          {/* Yellow card lines */}
          {yellows && yellows.overLines.length > 0 && (
            <div className="rounded-lg border border-white/5 bg-neutral-800/30 p-2">
              <div className="text-[10px] uppercase text-neutral-500 font-semibold mb-1">
                Cartões Amarelos — Mercados Over
              </div>
              {yellows.overLines.map((line, i) => (
                <MarketLineRow key={i} line={line} />
              ))}
            </div>
          )}

          {/* Red cards & penalties */}
          {(reds || penalties) && (
            <div className="rounded-lg border border-white/5 bg-neutral-800/30 p-2">
              <div className="text-[10px] uppercase text-neutral-500 font-semibold mb-1">
                Eventos Raros
              </div>
              {reds && (
                <YesNoBadge
                  label="Cartão Vermelho"
                  prob={reds.yesProb}
                  oddsFair={reds.yesOddsFair}
                  recommendation={reds.recommendation}
                  confidence={reds.confidence}
                />
              )}
              {penalties && (
                <YesNoBadge
                  label="Pênalti"
                  prob={penalties.yesProb}
                  oddsFair={penalties.yesOddsFair}
                  recommendation={penalties.recommendation}
                  confidence={penalties.confidence}
                />
              )}
            </div>
          )}

          {/* Fouls */}
          {fouls && fouls.overLines.length > 0 && (
            <div className="rounded-lg border border-white/5 bg-neutral-800/30 p-2">
              <div className="text-[10px] uppercase text-neutral-500 font-semibold mb-1">
                Faltas — Esperado FT: {fouls.expectedTotal.toFixed(1)}
              </div>
              {fouls.overLines.map((line, i) => (
                <MarketLineRow key={i} line={line} />
              ))}
            </div>
          )}

          {/* Metadata */}
          {yellows?.metadata && (
            <div className="text-[10px] text-neutral-500 text-center">
              Baseado em perfil do árbitro aos {currentMinute}′ | λ cartões = {yellows.metadata.cardLambda}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
