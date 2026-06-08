import { useMemo } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";

const SUPERBET_MARKET: Record<string, string> = {
  h2h: "Resultado Final",
  over_2_5: "Total de Gols → Mais de 2.5",
  over_3_5: "Total de Gols → Mais de 3.5",
  btts: "Ambas as Equipes Marcam",
  next_goal: "2º Gol",
};

function ev(prob: number, odd: number): number {
  return prob * odd - 1;
}

function implied(odd: number): number {
  return 1 / Math.max(odd, 1.01);
}

interface Insight {
  tone: "ok" | "warn" | "neutral";
  title: string;
  body: string;
}

function pickHouseFavorite(data: SuperbetLiveAdvice): {
  key: "1" | "X" | "2";
  team: string;
  odd: number;
  implied: number;
} | null {
  const entries = (["1", "X", "2"] as const)
    .map((key) => ({
      key,
      odd: data.h2hOdds[key],
      implied: data.h2hImplied[key],
    }))
    .filter((e) => e.odd != null && e.odd > 1);
  if (entries.length === 0) return null;
  const best = entries.reduce((a, b) => (a.odd! < b.odd! ? a : b));
  const team =
    best.key === "1" ? data.homeTeam : best.key === "2" ? data.awayTeam : "Empate";
  return {
    key: best.key,
    team,
    odd: best.odd!,
    implied: best.implied ?? implied(best.odd!),
  };
}

function pickModelFavorite(data: SuperbetLiveAdvice): {
  key: "1" | "X" | "2";
  team: string;
  prob: number;
} {
  const s = data.inplaySummary;
  const rows = [
    { key: "1" as const, team: data.homeTeam, prob: s.probFinalHome },
    { key: "X" as const, team: "Empate", prob: s.probFinalDraw },
    { key: "2" as const, team: data.awayTeam, prob: s.probFinalAway },
  ];
  return rows.reduce((a, b) => (b.prob > a.prob ? b : a));
}

function buildCrossInsights(data: SuperbetLiveAdvice): Insight[] {
  const s = data.inplaySummary;
  const insights: Insight[] = [];
  const btts = s.btts ?? 0;
  const over25 = s.over25 ?? 0;
  const [homeGoals, awayGoals] = (data.currentScore ?? "0x0")
    .split("x")
    .map((n) => Number.parseInt(n.trim(), 10) || 0);

  if (btts > 0.45 && over25 > 0.45) {
    insights.push({
      tone: "warn",
      title: "BTTS + Over 2.5 correlacionados",
      body:
        "Quando ambos marcam, o jogo tende a passar de 2.5 gols (pesquisa: correlação positiva ~20–35%). " +
        "Não empilhe as duas apostas no mesmo bilhete — escolha só a de maior EV em “O que fazer agora”.",
    });
  }

  if (btts < 0.2 && over25 < 0.2) {
    insights.push({
      tone: "neutral",
      title: "Jogo fechado no modelo",
      body: `BTTS ${formatPercent(btts)} e Over 2.5 ${formatPercent(over25)} — cenário de poucos gols restantes. ` +
        `Na Superbet, prefira Under / BTTS Não se algum dia tiver EV+, não “Ambas Marcam”.`,
    });
  }

  if (homeGoals !== awayGoals && Math.max(homeGoals, awayGoals) >= 1) {
    const leader = homeGoals > awayGoals ? data.homeTeam : data.awayTeam;
    const trailer = homeGoals > awayGoals ? data.awayTeam : data.homeTeam;
    insights.push({
      tone: "neutral",
      title: `Placar ${data.currentScore?.replace("x", "×")} — ${leader} na frente`,
      body:
        `${trailer} precisa reagir para BTTS subir. Próximo gol de ${trailer} muda totais e BTTS; ` +
        `favorito ${leader} com odd curta raramente dá EV+ (armadilha de odd 1.0x).`,
    });
  }

  const house = pickHouseFavorite(data);
  const model = pickModelFavorite(data);
  if (house && house.key === model.key && house.odd < 1.15) {
    insights.push({
      tone: "warn",
      title: "Casa e modelo concordam, mas odd curta",
      body:
        `Superbet e modelo apontam ${house.team}, porém odd ${house.odd.toFixed(2)} paga pouco — ` +
        "EV costuma ficar negativo mesmo com edge em pontos percentuais. Aguarde gol ou mercado de gols.",
    });
  }

  const top = data.strategy?.opportunities[0];
  if (top && top.tier !== "abaixo_limiar") {
    insights.push({
      tone: "ok",
      title: "Oportunidade com edge",
      body: `${top.label} @ ${top.marketOdd.toFixed(2)} com EV +${(top.expectedValue * 100).toFixed(1)}%. ` +
        `Stake sugerida: ${top.suggestedStakePct}% (R$ ${top.suggestedStakeValue.toFixed(0)}).`,
    });
  }

  if (!top && (data.strategy?.opportunityCount ?? 0) === 0) {
    insights.push({
      tone: "warn",
      title: "Sem valor agora — aguardar é a jogada",
      body:
        "Literatura de EV in-play: não force entrada quando todos os mercados mapeados têm EV ≤ 0. " +
        "Reavalie após gol, cartão vermelho ou mudança de odd (refresh ~25s).",
    });
  }

  return insights;
}

function buildPlaybook(data: SuperbetLiveAdvice): {
  action: "bet" | "wait" | "finished";
  steps: string[];
  superbetMarket?: string;
  pick?: string;
  stake?: string;
} {
  if (data.isFinished) {
    return {
      action: "finished",
      steps: [
        "Jogo encerrado — não há mais apostas in-play neste evento.",
        "Confira na Superbet se seus bilhetes ganharam ou perderam.",
        "Use o histórico do Bolão AI ou ‘Ver análise completa’ para revisar o confronto.",
      ],
    };
  }

  const top =
    data.strategy?.opportunities.find((o) => o.tier === "forte" || o.tier === "moderada" || o.tier === "leve") ??
    data.strategy?.opportunities[0];

  if (top && (top.tier === "forte" || top.tier === "moderada" || top.tier === "leve")) {
    const marketName = SUPERBET_MARKET[top.market] ?? top.market;
    return {
      action: "bet",
      superbetMarket: marketName,
      pick: top.label,
      stake: `R$ ${top.suggestedStakeValue.toFixed(0)} (${top.suggestedStakePct}% da banca)`,
      steps: [
        `Abra o jogo na Superbet (evento #${data.superbetEventId}).`,
        `Menu de mercados → ${marketName}.`,
        `Selecione: ${top.label} (odd alvo ~${top.marketOdd.toFixed(2)}).`,
        `Stake: R$ ${top.suggestedStakeValue.toFixed(0)} — no máximo ${top.suggestedStakePct}% da sua banca.`,
        "Confirme só se a odd ainda estiver próxima da captura (±3%). Se caiu muito, aguarde o próximo refresh.",
        "Não combine com outro mercado correlacionado no mesmo bilhete (ex.: BTTS + Over 2.5).",
      ],
    };
  }

  const bestWatch = data.strategy?.watchList[0];
  return {
    action: "wait",
    steps: [
      "Abra a Superbet e deixe o jogo visível, mas não aposte agora.",
      data.strategy?.waitReason ??
        "Nenhum mercado com EV positivo suficiente neste minuto.",
      "Fique de olho em gol, pênalti ou expulsão — isso recalcula BTTS, totais e 2º Gol.",
      "Volte a esta tela após o evento ou em ~25s (refresh automático).",
      bestWatch
        ? `Mercado menos ruim agora: ${bestWatch.label} @ ${bestWatch.marketOdd.toFixed(2)} (EV ${(bestWatch.expectedValue * 100).toFixed(1)}%) — ainda abaixo do limiar.`
        : "Quando “O que fazer agora” ficar verde, siga o passo a passo que aparecerá aqui.",
    ],
  };
}

interface LiveStrategyDashboardProps {
  data: SuperbetLiveAdvice;
}

export function LiveStrategyDashboard({ data }: LiveStrategyDashboardProps) {
  const playbook = useMemo(() => buildPlaybook(data), [data]);
  const house = useMemo(() => pickHouseFavorite(data), [data]);
  const modelFav = useMemo(() => pickModelFavorite(data), [data]);
  const crossInsights = useMemo(() => buildCrossInsights(data), [data]);

  const bttsYes = data.bttsOdds.yes;
  const bttsNo = data.bttsOdds.no;
  const bttsModel = data.inplaySummary.btts;
  const bttsYesEv = bttsModel != null && bttsYes ? ev(bttsModel, bttsYes) : null;
  const bttsNoEv =
    bttsModel != null && bttsNo ? ev(1 - bttsModel, bttsNo) : null;

  const agree =
    house && house.key === modelFav.key
      ? "Casa e modelo concordam"
      : house
        ? "Casa e modelo divergem"
        : "Sem 1X2 na API";

  if (data.isFinished) {
    return (
      <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-5">
        <h2 className="text-sm font-semibold text-white">Jogo finalizado</h2>
        <p className="mt-2 text-sm text-slate-400">
          Placar final {data.currentScore?.replace("x", " × ")}. As seções abaixo mostram o último
          snapshot; não use para novas apostas.
        </p>
      </section>
    );
  }

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-neon-blue/25 bg-neon-blue/[0.06] p-5">
        <h2 className="text-sm font-semibold text-white">Como apostar na Superbet</h2>
        <p className="mt-1 text-xs text-slate-400">
          Passo a passo {playbook.action === "bet" ? "para a entrada recomendada" : "enquanto aguarda"}
        </p>
        <ol className="mt-4 list-decimal space-y-2 pl-4 text-sm text-slate-300">
          {playbook.steps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        {playbook.action === "bet" && (
          <div className="mt-4 rounded-xl border border-neon-green/30 bg-neon-green/10 px-4 py-3 text-sm text-neon-green">
            <p className="font-semibold">Resumo rápido</p>
            <p className="mt-1 text-slate-200">
              {playbook.superbetMarket} → {playbook.pick} · {playbook.stake}
            </p>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-violet-500/20 bg-violet-500/[0.05] p-5">
        <h2 className="text-sm font-semibold text-white">Quem a casa aposta vs o que você deve fazer</h2>
        <p className="mt-1 text-xs text-slate-500">
          {agree} — edge positivo só vale se a odd pagar (EV+)
        </p>

        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <RoleCard
            role="Superbet (casa)"
            headline={house ? `${house.team} favorito` : "1X2 indisponível"}
            detail={
              house
                ? `Odd ${house.odd.toFixed(2)} = implícita ${formatPercent(house.implied)}. A casa lucra na margem embutida.`
                : "Use Total de Gols ou 2º Gol neste momento."
            }
            tone="house"
          />
          <RoleCard
            role="Nosso modelo"
            headline={`${modelFav.team} ${formatPercent(modelFav.prob)}`}
            detail="Probabilidade final condicionada ao placar e minuto."
            tone="model"
          />
          <RoleCard
            role="Você (agora)"
            headline={
              playbook.action === "bet"
                ? `Apostar: ${playbook.pick}`
                : "Não apostar"
            }
            detail={
              playbook.action === "bet"
                ? `${playbook.stake} — só se a odd na Superbet ainda for justa.`
                : "Todos os mercados mapeados estão sem EV+ suficiente. Aguardar protege a banca."
            }
            tone={playbook.action === "bet" ? "you-bet" : "you-wait"}
          />
        </div>

        {house && data.marketBenchmark?.h2h?.[house.key] && (
          <p className="mt-3 text-xs text-slate-400">
            Edge modelo vs mercado em {house.team}:{" "}
            <span
              className={
                data.marketBenchmark.h2h[house.key].edge > 0
                  ? "text-neon-green"
                  : "text-red-400"
              }
            >
              {(data.marketBenchmark.h2h[house.key].edge * 100).toFixed(1)} pp
            </span>
            {house.odd < 1.12 && (
              <span className="text-amber-300">
                {" "}
                — odd curta: edge em pp não vira lucro (EV pode ser negativo).
              </span>
            )}
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-white/8 bg-white/[0.02] p-5">
        <h2 className="text-sm font-semibold text-white">BTTS — Ambas as Equipes Marcam</h2>
        <p className="mt-1 text-xs text-slate-500">
          Modelo vs Superbet · correlação com Over 2.5
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricBox label="Modelo — ambos marcam" value={formatPercent(bttsModel ?? 0)} />
          <MetricBox
            label="Modelo — Over 2.5"
            value={formatPercent(data.inplaySummary.over25 ?? 0)}
          />
          {bttsYes != null && (
            <MetricBox
              label="Superbet — Sim"
              value={`${bttsYes.toFixed(2)} (${formatPercent(implied(bttsYes))})`}
              sub={
                bttsYesEv != null
                  ? `EV ${bttsYesEv >= 0 ? "+" : ""}${(bttsYesEv * 100).toFixed(1)}%`
                  : undefined
              }
              subTone={bttsYesEv != null && bttsYesEv > 0.04 ? "good" : "bad"}
            />
          )}
          {bttsNo != null && (
            <MetricBox
              label="Superbet — Não"
              value={`${bttsNo.toFixed(2)} (${formatPercent(implied(bttsNo))})`}
              sub={
                bttsNoEv != null
                  ? `EV ${bttsNoEv >= 0 ? "+" : ""}${(bttsNoEv * 100).toFixed(1)}%`
                  : undefined
              }
              subTone={bttsNoEv != null && bttsNoEv > 0.04 ? "good" : "bad"}
            />
          )}
        </div>

        <div className="mt-4 rounded-xl border border-white/8 bg-white/[0.03] px-4 py-3 text-sm text-slate-300">
          <p className="font-medium text-white">Leitura tática</p>
          <p className="mt-2">
            {(bttsModel ?? 0) < 0.25 ? (
              <>
                Com BTTS em {formatPercent(bttsModel ?? 0)}, o modelo vê pouca chance de{" "}
                <strong>{data.awayTeam}</strong> e <strong>{data.homeTeam}</strong> marcarem neste
                jogo. Na Superbet, abra <strong>Ambas as Equipes Marcam</strong> só se “O que fazer
                agora” indicar — caso contrário, ignore BTTS Sim.
              </>
            ) : (bttsModel ?? 0) > 0.55 ? (
              <>
                BTTS elevado ({formatPercent(bttsModel ?? 0)}) — se Over 2.5 também estiver alto,
                não duplique no mesmo bilhete; mercados correlacionados reduzem o edge líquido.
              </>
            ) : (
              <>
                BTTS neutro. Cruze com o placar: quem está perdendo precisa marcar para BTTS Sim
                subir ao vivo.
              </>
            )}
          </p>
        </div>
      </section>

      <section className="rounded-2xl border border-amber-500/20 bg-amber-500/[0.04] p-5">
        <h2 className="text-sm font-semibold text-white">Cruzamento de mercados (estratégia)</h2>
        <p className="mt-1 text-xs text-slate-500">
          Combina modelo, odds e correlações usadas em literatura de EV in-play
        </p>
        <ul className="mt-4 space-y-3">
          {crossInsights.map((item) => (
            <li
              key={item.title}
              className={`rounded-xl border px-4 py-3 text-sm ${
                item.tone === "ok"
                  ? "border-neon-green/25 bg-neon-green/8 text-slate-200"
                  : item.tone === "warn"
                    ? "border-amber-500/25 bg-amber-500/8 text-slate-200"
                    : "border-white/8 bg-white/[0.02] text-slate-300"
              }`}
            >
              <p className="font-semibold text-white">{item.title}</p>
              <p className="mt-1 text-xs leading-relaxed opacity-90">{item.body}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function RoleCard({
  role,
  headline,
  detail,
  tone,
}: {
  role: string;
  headline: string;
  detail: string;
  tone: "house" | "model" | "you-bet" | "you-wait";
}) {
  const border =
    tone === "house"
      ? "border-violet-500/30"
      : tone === "model"
        ? "border-neon-blue/30"
        : tone === "you-bet"
          ? "border-neon-green/35"
          : "border-amber-500/30";
  return (
    <div className={`rounded-xl border ${border} bg-white/[0.03] px-4 py-3`}>
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{role}</p>
      <p className="mt-1 text-base font-semibold text-white">{headline}</p>
      <p className="mt-1 text-xs text-slate-400">{detail}</p>
    </div>
  );
}

function MetricBox({
  label,
  value,
  sub,
  subTone,
}: {
  label: string;
  value: string;
  sub?: string;
  subTone?: "good" | "bad";
}) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-3">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-sm font-semibold text-white">{value}</p>
      {sub && (
        <p
          className={`mt-1 text-xs ${
            subTone === "good" ? "text-neon-green" : subTone === "bad" ? "text-red-400" : "text-slate-400"
          }`}
        >
          {sub}
        </p>
      )}
    </div>
  );
}
