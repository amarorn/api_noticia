import { useQuery } from "@tanstack/react-query";
import { getWcGroupStandingsUseCase, getHealthUseCase } from "@/application/container";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { HeroPageHeader } from "@/presentation/components/layout/PageHeader";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { TeamFlag } from "@/presentation/components/ui/TeamFlag";

export function WcGroupsPage() {
  const standingsQuery = useQuery({
    queryKey: ["wc-group-standings"],
    queryFn: () => getWcGroupStandingsUseCase.execute(),
    staleTime: 10 * 60_000,
  });

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: () => getHealthUseCase.execute(),
    staleTime: 60_000,
  });

  const artifact = healthQuery.data?.wcArtifact;

  return (
    <PageTransition>
      <HeroPageHeader
        title="Classificação simulada"
        subtitle="Tabela por grupo: projeção do modelo (Pts) e pontos reais do dia (Pts R)."
      />

      {artifact && (
        <div className="glass-card grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
          <Metric label="Holdout 2022" value={formatPct(artifact.holdoutAccuracy)} />
          <Metric label="Brier ensemble" value={artifact.ensembleBrier?.toFixed(3) ?? "—"} />
          <Metric
            label="Pesos DC / Log"
            value={
              artifact.ensembleWeights
                ? `${Math.round((artifact.ensembleWeights.dixon_coles ?? 0) * 100)}% / ${Math.round((artifact.ensembleWeights.logistic ?? 0) * 100)}%`
                : "—"
            }
          />
          <Metric label="Features" value={String(artifact.featureCount ?? "—")} />
        </div>
      )}

      {standingsQuery.isPending && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-64 rounded-xl" />
          ))}
        </div>
      )}

      {standingsQuery.isError && (
        <ErrorState
          title="Não foi possível carregar as tabelas"
          message="Confirme se a API está no ar e se o modelo WC foi treinado."
          onRetry={() => standingsQuery.refetch()}
        />
      )}

      {standingsQuery.data && (
        <>
          <p className="text-xs text-slate-500">
            {standingsQuery.data.note}
            {standingsQuery.data.nRealResults === 0 ? (
              <span className="text-slate-400"> · Nenhum jogo oficial com placar até hoje.</span>
            ) : null}
          </p>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {standingsQuery.data.groups.map((block) => (
              <div key={block.group} className="glass-card overflow-hidden">
                <div className="border-b border-white/6 bg-neon-green/5 px-4 py-3">
                  <h2 className="text-lg font-bold text-white">Grupo {block.group}</h2>
                </div>
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="text-slate-500">
                      <th className="px-3 py-2">#</th>
                      <th className="px-2 py-2">Seleção</th>
                      <th className="px-1 py-2 text-center">J</th>
                      <th className="px-1 py-2 text-center" title="Projeção do modelo">
                        Pts
                      </th>
                      <th className="px-1 py-2 text-center" title="Placares reais até hoje">
                        Pts R
                      </th>
                      <th className="px-1 py-2 text-center">SG</th>
                    </tr>
                  </thead>
                  <tbody>
                    {block.standings.map((row) => (
                      <tr
                        key={row.team}
                        className={`border-t border-white/5 ${
                          row.position <= 2 ? "bg-neon-green/5" : ""
                        }`}
                      >
                        <td className="px-3 py-2 font-bold text-slate-400">{row.position}</td>
                        <td className="px-2 py-2">
                          <span className="flex items-center gap-2 font-medium text-white">
                            <TeamFlag team={row.team} size={18} />
                            <span className="truncate">{row.team}</span>
                          </span>
                        </td>
                        <td className="px-1 py-2 text-center text-slate-400">{row.played}</td>
                        <td className="px-1 py-2 text-center font-bold text-neon-green">
                          {row.points}
                        </td>
                        <td
                          className={`px-1 py-2 text-center font-bold ${
                            row.realPoints > 0 ? "text-amber-300" : "text-slate-500"
                          }`}
                          title={
                            row.realPlayed > 0
                              ? `${row.realPlayed} jogo(s) · SG ${row.realGd}`
                              : "Sem jogos oficiais disputados"
                          }
                        >
                          {row.realPoints}
                        </td>
                        <td className="px-1 py-2 text-center text-slate-400">{row.gd}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </>
      )}
    </PageTransition>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-widest text-slate-500">{label}</p>
      <p className="text-lg font-bold text-white">{value}</p>
    </div>
  );
}

function formatPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}
