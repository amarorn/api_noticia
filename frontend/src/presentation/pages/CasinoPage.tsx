import { useQuery } from "@tanstack/react-query";
import { PageTransition } from "@/presentation/components/layout/PageTransition";
import { PageHeader } from "@/presentation/components/layout/PageHeader";
import { ErrorState } from "@/presentation/components/ui/EmptyState";
import { Skeleton } from "@/presentation/components/ui/Skeleton";
import { IconChevronRight, IconInfo } from "@/presentation/components/ui/Icons";
import { apiFetch } from "@/infrastructure/api/client";

interface CasinoGame {
  seo_id: string;
  title: string;
  slug: string;
  provider_id: string;
  integrator: string;
  min_stake: number;
  has_demo: boolean;
  has_anonymous_demo: boolean;
  product: string;
  game_category: string | null;
  studio: string | null;
  image_url: string | null;
  superbet_url: string;
  tags: string[];
  note: string | null;
}

interface CasinoCatalogResponse {
  count: number;
  seo_ids: string[];
  games: CasinoGame[];
  captured_at: string;
  betting_note: string;
}

function formatBrl(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function CasinoGameCard({ game }: { game: CasinoGame }) {
  return (
    <article
      className="group relative flex flex-col overflow-hidden rounded-2xl border border-white/8 bg-slate-900/60 transition hover:border-neon-green/25 hover:shadow-[0_0_32px_rgba(0,245,160,0.08)]"
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-slate-950">
        {game.image_url ? (
          <img
            src={game.image_url}
            alt={game.title}
            className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center font-mono text-xs text-slate-600">
            Sem imagem
          </div>
        )}
        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-4 pt-12">
          <p className="font-display text-lg font-bold text-white">{game.title}</p>
          <p className="font-mono text-[10px] uppercase tracking-widest text-slate-400">
            {game.studio ?? game.integrator} · {game.product.replace("_", " ")}
          </p>
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex flex-wrap gap-2">
          {game.tags.slice(0, 3).map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400"
            >
              {tag}
            </span>
          ))}
        </div>

        <dl className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <dt className="text-slate-500">Aposta mín.</dt>
            <dd className="font-semibold text-neon-green">{formatBrl(game.min_stake)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Mesa / ID</dt>
            <dd className="truncate font-mono text-slate-300" title={game.provider_id}>
              {game.provider_id}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Demo</dt>
            <dd className="text-slate-300">{game.has_demo ? "Sim" : "Não"}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Categoria</dt>
            <dd className="text-slate-300">{game.game_category ?? "—"}</dd>
          </div>
        </dl>

        {game.note ? (
          <p className="text-xs leading-relaxed text-slate-400">{game.note}</p>
        ) : null}

        <a
          href={game.superbet_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-auto inline-flex items-center justify-center gap-2 rounded-xl bg-neon-green/15 px-4 py-2.5 text-sm font-semibold text-neon-green transition hover:bg-neon-green/25"
        >
          Jogar na Superbet
          <IconChevronRight className="h-4 w-4" />
        </a>
      </div>
    </article>
  );
}

const BACBO_TABLE_ID = "SuperbetBacBo001";

interface BacboRound {
  round_id: string;
  table_id: string;
  winner: "player" | "banker" | "tie";
  player_score: number | null;
  banker_score: number | null;
  captured_at: string | null;
}

interface BacboRoundsResponse {
  table_id: string | null;
  count: number;
  stats: Record<string, number>;
  rounds: BacboRound[];
  updated_at: string | null;
}

const WINNER_STYLE: Record<string, { label: string; className: string }> = {
  player: { label: "P", className: "bg-sky-500/20 text-sky-300 border-sky-500/30" },
  banker: { label: "B", className: "bg-rose-500/20 text-rose-300 border-rose-500/30" },
  tie: { label: "T", className: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30" },
};

function BacBoMonitorPanel() {
  const roundsQuery = useQuery({
    queryKey: ["casino-bacbo-rounds", BACBO_TABLE_ID],
    queryFn: () =>
      apiFetch<BacboRoundsResponse>(
        `/casino/bacbo/rounds?table_id=${encodeURIComponent(BACBO_TABLE_ID)}&limit=40`,
      ),
    refetchInterval: 5_000,
  });

  const stats = roundsQuery.data?.stats ?? {};
  const rounds = roundsQuery.data?.rounds ?? [];

  return (
    <section className="rounded-2xl border border-white/8 bg-slate-900/50 p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-bold text-white">Monitor Bac Bo</h2>
          <p className="text-xs text-slate-400">
            Rodadas capturadas pela extensão v1.9+ com o jogo aberto na Superbet
          </p>
        </div>
        {roundsQuery.data?.updated_at ? (
          <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">
            Lake · {new Date(roundsQuery.data.updated_at).toLocaleString("pt-BR")}
          </p>
        ) : null}
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2 sm:max-w-md">
        {(["player", "banker", "tie"] as const).map((key) => (
          <div
            key={key}
            className={`rounded-xl border px-3 py-2 text-center ${WINNER_STYLE[key].className}`}
          >
            <p className="font-mono text-[10px] uppercase opacity-70">{key}</p>
            <p className="text-xl font-bold">{stats[key] ?? 0}</p>
          </div>
        ))}
      </div>

      {rounds.length > 0 ? (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {rounds.slice(0, 36).map((round) => {
            const style = WINNER_STYLE[round.winner] ?? WINNER_STYLE.player;
            const score =
              round.player_score != null && round.banker_score != null
                ? `${round.player_score}-${round.banker_score}`
                : style.label;
            return (
              <span
                key={round.round_id}
                title={`${round.winner} · ${round.captured_at ?? ""}`}
                className={`inline-flex min-w-[2.25rem] items-center justify-center rounded-md border px-1.5 py-1 font-mono text-[11px] font-bold ${style.className}`}
              >
                {score}
              </span>
            );
          })}
        </div>
      ) : (
        <p className="mb-4 text-sm text-slate-500">
          Nenhuma rodada ainda. Abra{" "}
          <a
            href="https://superbet.bet.br/jogo/bac-bo-superbet/379099"
            target="_blank"
            rel="noopener noreferrer"
            className="text-neon-green hover:underline"
          >
            Bac Bo na Superbet
          </a>{" "}
          com a extensão recarregada — o hook escuta o WebSocket Evolution.
        </p>
      )}

      {rounds.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-white/5">
          <table className="min-w-full text-left text-xs">
            <thead className="bg-white/5 text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">Horário</th>
                <th className="px-3 py-2 font-medium">Vencedor</th>
                <th className="px-3 py-2 font-medium">Placar</th>
              </tr>
            </thead>
            <tbody>
              {rounds.slice(0, 12).map((round) => (
                <tr key={round.round_id} className="border-t border-white/5">
                  <td className="px-3 py-2 text-slate-400">
                    {round.captured_at
                      ? new Date(round.captured_at).toLocaleTimeString("pt-BR")
                      : "—"}
                  </td>
                  <td className="px-3 py-2 capitalize text-slate-200">{round.winner}</td>
                  <td className="px-3 py-2 font-mono text-slate-300">
                    {round.player_score != null && round.banker_score != null
                      ? `${round.player_score} × ${round.banker_score}`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

export function CasinoPage() {
  const catalogQuery = useQuery({
    queryKey: ["casino-catalog"],
    queryFn: () => apiFetch<CasinoCatalogResponse>("/casino/games"),
    staleTime: 5 * 60_000,
  });

  return (
    <PageTransition>
      <div className="mx-auto max-w-6xl space-y-6 px-2 pb-10 sm:px-4">
        <PageHeader
          title="Casino"
          subtitle="Catálogo live casino Superbet — metadados e link direto para jogar"
          badge="Evolution"
          badgeColor="purple"
        />

        <div
          className="flex gap-3 rounded-xl border border-neon-blue/15 bg-neon-blue/5 px-4 py-3 text-sm text-slate-300"
          role="note"
        >
          <IconInfo className="mt-0.5 h-4 w-4 shrink-0 text-neon-blue" />
          <div className="space-y-1">
            <p>
              O Bolão AI lista jogos via API pública da Superbet. Para apostar, abra o jogo logado
              em{" "}
              <a
                href="https://superbet.bet.br"
                target="_blank"
                rel="noopener noreferrer"
                className="text-neon-blue underline-offset-2 hover:underline"
              >
                superbet.bet.br
              </a>
              — as fichas são enviadas pelo WebSocket Evolution, não por bilhete esportivo.
            </p>
            {catalogQuery.data?.betting_note ? (
              <p className="text-xs text-slate-500">{catalogQuery.data.betting_note}</p>
            ) : null}
          </div>
        </div>

        <BacBoMonitorPanel />

        {catalogQuery.isPending ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2].map((i) => (
              <Skeleton key={i} className="h-80 rounded-2xl" />
            ))}
          </div>
        ) : null}

        {catalogQuery.isError ? (
          <ErrorState
            title="Catálogo indisponível"
            message="Não foi possível carregar os jogos casino da Superbet."
          />
        ) : null}

        {catalogQuery.data ? (
          <>
            <p className="font-mono text-[11px] uppercase tracking-widest text-slate-500">
              {catalogQuery.data.count} jogo(s) · atualizado{" "}
              {new Date(catalogQuery.data.captured_at).toLocaleString("pt-BR")}
            </p>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {catalogQuery.data.games.map((game) => (
                <CasinoGameCard key={game.seo_id} game={game} />
              ))}
            </div>
          </>
        ) : null}
      </div>
    </PageTransition>
  );
}
