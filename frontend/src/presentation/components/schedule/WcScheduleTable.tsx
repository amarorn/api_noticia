import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import type { WcSchedule, WcScheduleMatch } from "@/domain/entities";
import { IconChevronRight } from "@/presentation/components/ui/Icons";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";

interface WcScheduleTableProps {
  schedule: WcSchedule;
  selectedRound: number | "all";
  selectedGroup: string | "all";
}

function formatKickoff(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function TeamCell({ name }: { name: string }) {
  return (
    <div className="flex items-center gap-2.5 min-w-0">
      <TeamFlag team={name} size={32} />
      <span className="truncate font-medium text-white">{name}</span>
    </div>
  );
}

function MatchRow({ match, index }: { match: WcScheduleMatch; index: number }) {
  return (
    <motion.tr
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03 }}
      className="group border-b border-white/5 transition-colors hover:bg-white/[0.03]"
    >
      <td className="px-4 py-3.5 text-xs text-slate-500 whitespace-nowrap">
        {formatKickoff(match.kickoff)}
      </td>
      <td className="px-4 py-3.5">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-neon-green/10 text-xs font-black text-neon-green">
          {match.group}
        </span>
      </td>
      <td className="px-4 py-3.5">
        <TeamCell name={match.homeTeam} />
      </td>
      <td className="px-2 py-3.5 text-center">
        <span className="text-[10px] font-black text-slate-600">×</span>
      </td>
      <td className="px-4 py-3.5">
        <TeamCell name={match.awayTeam} />
      </td>
      <td className="hidden px-4 py-3.5 text-xs text-slate-500 lg:table-cell">
        <span className="block truncate">{match.venue ?? "—"}</span>
        {match.city && (
          <span className="block truncate text-[10px] text-slate-600">{match.city}</span>
        )}
      </td>
      <td className="px-4 py-3.5 text-right">
        <Link
          to={`/match/${encodeURIComponent(match.homeTeam)}/${encodeURIComponent(match.awayTeam)}`}
          className="inline-flex items-center gap-1 rounded-lg border border-white/8 bg-white/4 px-2.5 py-1.5 text-[11px] font-medium text-slate-400 opacity-0 transition-all group-hover:opacity-100 hover:border-neon-green/30 hover:text-neon-green"
        >
          Palpite
          <IconChevronRight className="h-3 w-3" />
        </Link>
      </td>
    </motion.tr>
  );
}

export function WcScheduleTable({
  schedule,
  selectedRound,
  selectedGroup,
}: WcScheduleTableProps) {
  const filtered = schedule.matches.filter((m) => {
    if (selectedRound !== "all" && m.round !== selectedRound) return false;
    if (selectedGroup !== "all" && m.group !== selectedGroup) return false;
    return true;
  });

  if (filtered.length === 0) {
    return (
      <div className="glass-card flex flex-col items-center justify-center gap-2 py-16 text-center">
        <p className="text-sm text-slate-400">Nenhum jogo encontrado com os filtros atuais.</p>
      </div>
    );
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-white/8 bg-white/[0.02] text-left text-[10px] font-bold uppercase tracking-widest text-slate-500">
              <th className="px-4 py-3">Data</th>
              <th className="px-4 py-3">Gr.</th>
              <th className="px-4 py-3">Mandante</th>
              <th className="px-2 py-3" />
              <th className="px-4 py-3">Visitante</th>
              <th className="hidden px-4 py-3 lg:table-cell">Estádio</th>
              <th className="px-4 py-3 text-right">Ação</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((match, i) => (
              <MatchRow key={match.matchId} match={match} index={i} />
            ))}
          </tbody>
        </table>
      </div>
      <div className="border-t border-white/5 px-4 py-2.5 text-[11px] text-slate-600">
        {filtered.length} jogo{filtered.length !== 1 ? "s" : ""} · {schedule.totalMatches} no total
      </div>
    </div>
  );
}

interface GroupGridProps {
  groups: WcSchedule["groups"];
  selectedGroup: string | "all";
  onSelectGroup: (group: string | "all") => void;
}

export function WcGroupGrid({ groups, selectedGroup, onSelectGroup }: GroupGridProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {groups.map((group) => {
        const active = selectedGroup === group.id;
        return (
          <button
            key={group.id}
            type="button"
            onClick={() => onSelectGroup(active ? "all" : group.id)}
            className={`glass-card-hover flex flex-col gap-3 p-4 text-left transition-all ${
              active ? "ring-1 ring-neon-green/40 bg-neon-green/5" : ""
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-widest text-slate-500">
                Grupo {group.id}
              </span>
              <span className="text-[10px] text-slate-600">{group.teams.length} times</span>
            </div>
            <ul className="space-y-2">
              {group.teams.map((team) => (
                <li key={team} className="flex items-center gap-2">
                  <TeamFlag team={team} size={20} />
                  <span className="truncate text-sm text-slate-300">{team}</span>
                </li>
              ))}
            </ul>
          </button>
        );
      })}
    </div>
  );
}
