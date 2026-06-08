import { useMemo, useState } from "react";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import { formatPercent } from "@/presentation/theme";

interface LivePlainGuideProps {
  data: SuperbetLiveAdvice;
  trackBet: boolean;
}

interface GuideBlock {
  label: string;
  text: string;
  tone?: "ok" | "warn" | "neutral";
}

function parseScore(score: string | null): [number, number] {
  const parts = (score ?? "0x0").split("x").map((n) => Number.parseInt(n.trim(), 10) || 0);
  return [parts[0] ?? 0, parts[1] ?? 0];
}

function buildGuide(data: SuperbetLiveAdvice, trackBet: boolean): GuideBlock[] {
  const blocks: GuideBlock[] = [];
  const s = data.inplaySummary;
  const [hg, ag] = parseScore(data.currentScore);
  const top = data.strategy?.opportunities[0];
  const avoid = (data.strategy?.shields ?? [])
    .filter((sh) => sh.action === "evitar")
    .map((sh) => sh.title.replace(/^Evitar /, ""));
  const threshold = (data.strategy?.minEdgeThreshold ?? 0.04) * 100;

  if (data.isFinished) {
    blocks.push({
      label: "Situação",
      text: `Jogo encerrado ${data.currentScore?.replace("x", "×") ?? ""}. Sem apostas in-play. Confira o resultado dos seus bilhetes na Superbet.`,
      tone: "neutral",
    });
    return blocks;
  }

  blocks.push({
    label: "Situação",
    text: `${data.homeTeam} ${hg}×${ag} ${data.awayTeam} · ${data.minute}'${data.periodLabel ? ` (${data.periodLabel})` : ""}. A tela atualiza a cada ~25s ou após gol.`,
    tone: "neutral",
  });

  if (trackBet && data.cashout) {
    const cashLabels: Record<string, string> = {
      cashout: "Considere cash-out total",
      cashout_parcial: "Considere cash-out parcial (50–70%)",
      manter: "Manter a aposta aberta",
      aguardar: "Aguardar e monitorar",
    };
    blocks.push({
      label: "Sua aposta aberta",
      text: `${cashLabels[data.cashout.action] ?? data.cashout.action}. ${data.cashout.reason} EV residual: ${(data.cashout.remainingEv * 100).toFixed(1)}%.`,
      tone: data.cashout.action.startsWith("cashout") ? "warn" : "ok",
    });
  }

  if (top && (top.tier === "forte" || top.tier === "moderada" || top.tier === "leve")) {
    const tierLabel =
      top.tier === "forte" ? "entrada forte" : top.tier === "moderada" ? "entrada moderada" : "entrada leve";
    blocks.push({
      label: "O que fazer",
      text:
        `Aposte em ${top.label} @ ${top.marketOdd.toFixed(2)} na Superbet (menu Resultado Final ou mercado indicado). ` +
        `Stake sugerida: R$ ${top.suggestedStakeValue.toFixed(0)} (${top.suggestedStakePct}% da banca). ` +
        `EV +${(top.expectedValue * 100).toFixed(1)}% — ${tierLabel}.`,
      tone: "ok",
    });
  } else {
    blocks.push({
      label: "O que fazer",
      text:
        data.strategy?.waitReason ??
        "Não aposte agora. Nenhum mercado passou o limiar de segurança (EV +4% ao vivo).",
      tone: "warn",
    });
  }

  if (avoid.length > 0) {
    blocks.push({
      label: "Evitar",
      text: `Não aposte em: ${avoid.join(", ")}. A casa precifica acima do modelo nesses lados.`,
      tone: "warn",
    });
  }

  const h2hKeys = Object.keys(data.h2hOdds);
  if (h2hKeys.length > 0) {
    const favKey = h2hKeys.reduce((a, b) =>
      (data.h2hOdds[a] ?? 99) < (data.h2hOdds[b] ?? 99) ? a : b,
    );
    const favTeam =
      favKey === "1" ? data.homeTeam : favKey === "2" ? data.awayTeam : "Empate";
    const favOdd = data.h2hOdds[favKey]!;
    blocks.push({
      label: "Quem a casa favorece",
      text:
        `Superbet favorece ${favTeam} (odd ${favOdd.toFixed(2)}). ` +
        `Modelo: ${formatPercent(
          favKey === "1" ? s.probFinalHome : favKey === "2" ? s.probFinalAway : s.probFinalDraw,
        )}. ` +
        (favOdd < 1.15
          ? "Odd curta: mesmo concordando com o favorito, o EV costuma ser negativo — não force entrada no 1X2 do líder."
          : "Compare com ‘O que fazer agora’ antes de apostar no favorito."),
      tone: favOdd < 1.15 ? "warn" : "neutral",
    });
  } else {
    blocks.push({
      label: "Odds 1X2",
      text: "Resultado Final indisponível neste refresh. Use Total de Gols, BTTS ou 2º Gol se o app indicar.",
      tone: "neutral",
    });
  }

  const btts = s.btts ?? 0;
  const over25 = s.over25 ?? 0;
  blocks.push({
    label: "BTTS e gols",
    text:
      btts < 0.2
        ? `BTTS ${formatPercent(btts)} e Over 2.5 ${formatPercent(over25)} — jogo fechado no modelo. Ignore BTTS Sim salvo ordem verde em ‘O que fazer agora’.`
        : btts > 0.5 && over25 > 0.5
          ? `BTTS ${formatPercent(btts)} e Over 2.5 ${formatPercent(over25)} — correlacionados. Não duplique no mesmo bilhete.`
          : `BTTS ${formatPercent(btts)}, Over 2.5 ${formatPercent(over25)}. Abra ‘Ambas Marcam’ só se o comando principal indicar.`,
    tone: "neutral",
  });

  const watch = data.strategy?.watchList?.[0];
  if (!top && watch) {
    blocks.push({
      label: "No radar",
      text: `Mais próximo do limiar: ${watch.label} @ ${watch.marketOdd.toFixed(2)} (EV ${(watch.expectedValue * 100).toFixed(1)}%, precisa +${threshold.toFixed(0)}%).`,
      tone: "neutral",
    });
  }

  blocks.push({
    label: "Regra de ouro",
    text: "Só aposte em mercados da coluna verde (Mercados na Superbet) e só quando ‘O que fazer agora’ estiver verde. Ignore a coluna amarela.",
    tone: "ok",
  });

  return blocks;
}

const TONE_CLASS: Record<string, string> = {
  ok: "border-neon-green/25 bg-neon-green/8",
  warn: "border-amber-500/25 bg-amber-500/8",
  neutral: "border-white/10 bg-white/[0.03]",
};

export function LivePlainGuide({ data, trackBet }: LivePlainGuideProps) {
  const [open, setOpen] = useState(false);
  const blocks = useMemo(() => buildGuide(data, trackBet), [data, trackBet]);

  return (
    <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-white/[0.04] to-transparent">
      {/* Cabeçalho colapsável */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
        aria-expanded={open}
      >
        <div>
          <h2 className="text-sm font-semibold text-white">
            Guia rápido — leia em 30 segundos
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Resumo em português claro. Clique para {open ? "fechar" : "expandir"}.
          </p>
        </div>
        <span
          className={`shrink-0 text-slate-500 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        >
          ▾
        </span>
      </button>

      {/* Conteúdo expandido */}
      {open && (
        <div className="border-t border-white/8 px-5 pb-5 pt-4">
          <dl className="space-y-3">
            {blocks.map((block) => (
              <div
                key={block.label}
                className={`rounded-xl border px-4 py-3 ${TONE_CLASS[block.tone ?? "neutral"]}`}
              >
                <dt className="text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  {block.label}
                </dt>
                <dd className="mt-1.5 text-sm leading-relaxed text-slate-200">{block.text}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </section>
  );
}
