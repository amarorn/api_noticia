import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getBrasileiraoRoundUseCase } from "@/application/container";
import { PageTransition, StaggerContainer, StaggerItem } from "@/presentation/components/layout/PageTransition";
import { HeroPageHeader } from "@/presentation/components/layout/PageHeader";
import { QuickActions } from "@/presentation/components/layout/QuickActions";
import { BrasileiraoCard } from "@/presentation/components/predictions/MatchCard";
import { DashboardSkeleton } from "@/presentation/components/ui/Skeleton";
import { EmptyState, ErrorState } from "@/presentation/components/ui/EmptyState";
import { IconCalendar, IconLive } from "@/presentation/components/ui/Icons";

export function DashboardPage() {
  const query = useQuery({
    queryKey: ["brasileirao-round"],
    queryFn: () => getBrasileiraoRoundUseCase.execute(),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
  });

  if (query.isLoading) {
    return (
      <PageTransition>
        <HeroPageHeader
          title="Brasileirão"
          subtitle="Carregando palpites da rodada…"
        />
        <DashboardSkeleton />
      </PageTransition>
    );
  }

  if (query.isError) {
    return (
      <PageTransition>
        <ErrorState
          title="Não foi possível carregar os palpites"
          message={
            query.error instanceof Error
              ? query.error.message
              : "Verifique se a API está rodando (./scripts/dev-api-stable.sh)"
          }
          onRetry={() => query.refetch()}
        />
      </PageTransition>
    );
  }

  const round = query.data!;
  const gamesLabel = `${round.predictions.length} ${round.predictions.length === 1 ? "jogo" : "jogos"}`;

  return (
    <PageTransition>
      <HeroPageHeader
        title={`${round.competition} — Rodada ${round.roundNumber}`}
        subtitle="Palpites 1/X/2 com notícias, tabela e forma recente"
        badges={[{ label: gamesLabel, color: "blue" }]}
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <QuickActions />
      </div>

      {round.predictions.length === 0 ? (
        <EmptyState
          title="Nenhum jogo na rodada"
          description="Edite data/rounds/current.json com os confrontos da rodada atual."
          icon={IconCalendar}
          iconColor="#00e0ff"
          action={
            <Link to="/noticias" className="btn-ghost mt-2">
              Ver notícias do campeonato
            </Link>
          }
        />
      ) : (
        <StaggerContainer className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {round.predictions.map((p, i) => (
            <StaggerItem key={`${p.homeTeam}-${p.awayTeam}`}>
              <BrasileiraoCard
                homeTeam={p.homeTeam}
                awayTeam={p.awayTeam}
                prediction={p.prediction}
                confidence={p.confidence}
                reason={p.reason}
                newsCount={p.newsCount}
                modelSource={p.modelSource}
                probabilities={p.probabilities}
                homePosition={p.homePosition}
                awayPosition={p.awayPosition}
                index={i}
              />
            </StaggerItem>
          ))}
        </StaggerContainer>
      )}

      <section className="mt-6 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-white">Jogos ao vivo na Superbet</p>
            <p className="mt-0.5 text-xs text-slate-500">
              Acompanhe campeonatos de clubes com odds e orientação in-play
            </p>
          </div>
          <Link
            to="/ao-vivo?sport=football"
            className="inline-flex items-center gap-2 rounded-xl border border-neon-green/25 bg-neon-green/10 px-3 py-2 text-xs font-semibold text-neon-green transition hover:bg-neon-green/15"
          >
            <IconLive className="h-3.5 w-3.5" />
            Abrir ao vivo
          </Link>
        </div>
      </section>

      <details className="group mt-4">
        <summary className="flex cursor-pointer items-center gap-2 text-xs text-slate-500 hover:text-slate-300 transition-colors select-none">
          <span className="inline-flex h-4 w-4 items-center justify-center rounded bg-neon-green/10 text-neon-green text-[10px]">?</span>
          Como ler estes palpites
          <span className="ml-auto text-[10px] opacity-50 group-open:hidden">[clique para expandir]</span>
        </summary>
        <div className="info-panel mt-2 p-3 text-[11px] leading-relaxed text-slate-400">
          <ul className="list-disc space-y-1 pl-4">
            <li><strong className="text-slate-300">Prob. palpite</strong> é a chance estimada do resultado (1/X/2).</li>
            <li>Modelo combina posição na tabela, forma recente e sentimento das notícias.</li>
            <li>Atualize <code className="text-slate-300">data/rounds/current.json</code> a cada rodada.</li>
          </ul>
        </div>
      </details>
    </PageTransition>
  );
}
