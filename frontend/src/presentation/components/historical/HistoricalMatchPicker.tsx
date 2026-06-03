import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { OutcomeLabel, WcHistoricalMatch } from "@/domain/entities";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { outcomeColors, outcomeLabels } from "@/presentation/theme";
import { formatMatchDate, teamFlag } from "@/presentation/utils/teamFlags";

interface HistoricalMatchPickerProps {
  matches: WcHistoricalMatch[] | undefined;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  selectedMatch: WcHistoricalMatch | null;
  onSelect: (match: WcHistoricalMatch) => void;
}

export function HistoricalMatchPicker({
  matches,
  isLoading,
  isError,
  onRetry,
  selectedMatch,
  onSelect,
}: HistoricalMatchPickerProps) {
  const [phaseFilter, setPhaseFilter] = useState("");
  const [search, setSearch] = useState("");

  const phaseOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const m of matches ?? []) {
      if (!map.has(m.phase)) map.set(m.phase, m.phaseLabel);
    }
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [matches]);

  const filteredMatches = useMemo(() => {
    const list = matches ?? [];
    const q = search.trim().toLowerCase();
    return list.filter((m) => {
      if (phaseFilter && m.phase !== phaseFilter) return false;
      if (!q) return true;
      return (
        m.homeTeam.toLowerCase().includes(q) ||
        m.awayTeam.toLowerCase().includes(q) ||
        m.score.includes(q)
      );
    });
  }, [matches, phaseFilter, search]);

  const totalCount = matches?.length ?? 0;

  return (
    <div className="glass-card overflow-hidden">
      <div className="border-b border-white/5 p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative min-w-0 flex-1">
            <SearchIcon className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              type="search"
              placeholder="Buscar time ou placar..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field pl-10"
            />
          </div>
          <p className="shrink-0 text-xs text-slate-500">
            {filteredMatches.length === totalCount ? (
              <span>{totalCount} jogos</span>
            ) : (
              <span>
                {filteredMatches.length} de {totalCount} jogos
              </span>
            )}
          </p>
        </div>

        {phaseOptions.length > 1 && (
          <div className="mt-4 flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
            <PhaseChip
              active={phaseFilter === ""}
              onClick={() => setPhaseFilter("")}
              label="Todas"
              count={totalCount}
            />
            {phaseOptions.map(([value, label]) => (
              <PhaseChip
                key={value}
                active={phaseFilter === value}
                onClick={() => setPhaseFilter(value)}
                label={label}
                count={(matches ?? []).filter((m) => m.phase === value).length}
              />
            ))}
          </div>
        )}
      </div>

      <div className="p-2 sm:p-3">
        {isLoading && <Skeleton className="h-72 w-full rounded-xl" />}
        {isError && (
          <ErrorState message="Erro ao carregar jogos da edição" onRetry={onRetry} />
        )}
        {!isLoading && !isError && matches && (
          <div className="max-h-[420px] space-y-1.5 overflow-y-auto pr-1 scrollbar-thin">
            {filteredMatches.length === 0 && (
              <EmptyState
                hasFilters={Boolean(search.trim() || phaseFilter)}
                onClear={() => {
                  setSearch("");
                  setPhaseFilter("");
                }}
              />
            )}
            {filteredMatches.map((match, index) => (
              <MatchRow
                key={match.matchId}
                match={match}
                index={index}
                selected={selectedMatch?.matchId === match.matchId}
                onSelect={() => onSelect(match)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PhaseChip({
  active,
  onClick,
  label,
  count,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition-all ${
        active
          ? "border-neon-blue/50 bg-neon-blue/15 text-neon-blue"
          : "border-white/10 bg-white/5 text-slate-400 hover:border-white/20 hover:text-slate-200"
      }`}
    >
      {label}
      <span className={`ml-1.5 ${active ? "text-neon-blue/70" : "text-slate-500"}`}>
        {count}
      </span>
    </button>
  );
}

function MatchRow({
  match,
  index,
  selected,
  onSelect,
}: {
  match: WcHistoricalMatch;
  index: number;
  selected: boolean;
  onSelect: () => void;
}) {
  const dateLabel = formatMatchDate(match.matchDate);

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index * 0.02, 0.3) }}
      onClick={onSelect}
      className={`group relative flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition-all sm:gap-4 sm:px-4 ${
        selected
          ? "border-neon-green/40 bg-neon-green/10 shadow-[inset_3px_0_0_0_#00ff88]"
          : "border-transparent bg-white/[0.03] hover:border-white/10 hover:bg-white/[0.06]"
      }`}
    >
      {selected && (
        <span className="absolute right-3 top-3 flex h-5 w-5 items-center justify-center rounded-full bg-neon-green/20 text-neon-green">
          <CheckIcon className="h-3 w-3" />
        </span>
      )}

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-center gap-2 sm:gap-4">
          <TeamLine name={match.homeTeam} align="left" />
          <ScoreBlock
            homeScore={match.homeScore}
            awayScore={match.awayScore}
            selected={selected}
          />
          <TeamLine name={match.awayTeam} align="right" />
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:hidden">
          {dateLabel && (
            <span className="text-[11px] uppercase tracking-wider text-slate-500">
              {dateLabel}
            </span>
          )}
          <PhaseBadge phaseLabel={match.phaseLabel} groupName={match.groupName} />
          <OutcomePill label={match.result} />
        </div>
      </div>

      <div className="hidden shrink-0 flex-col items-end gap-1 sm:flex">
        {dateLabel && (
          <span className="text-[11px] uppercase tracking-wider text-slate-500">
            {dateLabel}
          </span>
        )}
        <PhaseBadge phaseLabel={match.phaseLabel} groupName={match.groupName} />
        <OutcomePill label={match.result} />
      </div>
    </motion.button>
  );
}

function TeamLine({ name, align }: { name: string; align: "left" | "right" }) {
  return (
    <div
      className={`flex min-w-0 flex-1 items-center gap-2 ${
        align === "right" ? "sm:justify-end sm:text-right" : ""
      }`}
    >
      {align === "left" && (
        <span className="text-lg leading-none" aria-hidden>
          {teamFlag(name)}
        </span>
      )}
      <span className="truncate text-sm font-semibold text-white sm:text-base">{name}</span>
      {align === "right" && (
        <span className="text-lg leading-none" aria-hidden>
          {teamFlag(name)}
        </span>
      )}
    </div>
  );
}

function ScoreBlock({
  homeScore,
  awayScore,
  selected,
}: {
  homeScore: number;
  awayScore: number;
  selected: boolean;
}) {
  return (
    <div
      className={`flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 font-mono text-lg font-bold tabular-nums ${
        selected ? "bg-neon-green/10 text-neon-green" : "bg-white/5 text-neon-blue"
      }`}
    >
      <span>{homeScore}</span>
      <span className="text-xs font-normal text-slate-500">×</span>
      <span>{awayScore}</span>
    </div>
  );
}

function PhaseBadge({
  phaseLabel,
  groupName,
}: {
  phaseLabel: string;
  groupName: string | null;
}) {
  const group = groupName && !groupName.startsWith("Grupo") ? `Grupo ${groupName}` : groupName;
  return (
    <span className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] text-slate-400">
      {phaseLabel}
      {group ? ` · ${group}` : ""}
    </span>
  );
}

function OutcomePill({ label }: { label: OutcomeLabel }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold"
      style={{ backgroundColor: `${outcomeColors[label]}22`, color: outcomeColors[label] }}
      title={outcomeLabels[label]}
    >
      {label}
    </span>
  );
}

function EmptyState({
  hasFilters,
  onClear,
}: {
  hasFilters: boolean;
  onClear: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-white/10 px-6 py-12 text-center">
      <p className="text-sm text-slate-400">
        {hasFilters
          ? "Nenhum jogo encontrado com os filtros aplicados."
          : "Nenhum jogo disponível nesta edição."}
      </p>
      {hasFilters && (
        <button type="button" onClick={onClear} className="btn-ghost mt-4 text-xs">
          Limpar filtros
        </button>
      )}
    </div>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}
