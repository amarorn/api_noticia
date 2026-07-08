import { useMemo } from "react";
import { Link } from "react-router-dom";
import type { SuperbetLiveAdvice } from "@/domain/entities";
import type { LiveAdviceScoreTick } from "@/presentation/hooks/useLiveAdviceQueries";
import {
  IconArrowLeft,
  IconMenu,
  IconRefreshCw,
} from "@/presentation/components/ui/Icons";
import {
  buildDataQualityReport,
} from "@/presentation/components/live-operational/dataQuality";
import {
  buildOperationalDecision,
  secondsSince,
} from "@/presentation/components/live-operational/liveOperationalUtils";
import { useMarketOperationalRows } from "@/presentation/components/live-operational/useMarketOperationalRows";
import { LiveMatchHeaderV2 } from "./live-match-header-v2";
import { LiveOperationalSummaryV2 } from "./live-operational-summary-v2";
import { LiveMarketsTableV2 } from "./live-markets-table-v2";
import { LiveDataQualityV2 } from "./live-data-quality-v2";
import "./live-visual-v2.css";

export type LiveTabV2 = "resumo" | "mercados" | "qualidade";

const TABS: Array<{ id: LiveTabV2; label: string }> = [
  { id: "resumo", label: "Resumo Operacional" },
  { id: "mercados", label: "Mercados" },
  { id: "qualidade", label: "Qualidade dos Dados" },
];

function fmtTime(iso: string | null | undefined) {
  if (!iso) return "--:--:--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "--:--:--";
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function LiveDashboardContentV2({
  data,
  scoreTick,
  eventId,
  bankroll,
  pollFastMs,
  isFetching,
  isAdvicePending,
  onRefresh,
  activeTab,
  onTabChange,
}: {
  data: SuperbetLiveAdvice;
  scoreTick: LiveAdviceScoreTick;
  eventId: number;
  bankroll: number;
  pollFastMs: number;
  isFetching: boolean;
  isAdvicePending: boolean;
  onRefresh: () => void;
  activeTab: LiveTabV2;
  onTabChange: (tab: LiveTabV2) => void;
}) {
  const decision = useMemo(() => buildOperationalDecision(data), [data]);
  const { rows, history } = useMarketOperationalRows(data);
  const quality = useMemo(
    () => buildDataQualityReport(data, rows, secondsSince(data.capturedAt)),
    [data, rows],
  );

  const title = activeTab === "qualidade" ? "Data Quality" : "Dashboard Overview";
  const subtitle = activeTab === "qualidade"
    ? "Monitore a confiabilidade e o frescor dos sinais em tempo real."
    : undefined;

  return (
    <div className="live-v2-shell w-full max-w-full space-y-5 overflow-x-hidden">
      <div className="text-center">
        <h1 className="v2-page-title">{title}</h1>
        {subtitle && <p className="v2-page-subtitle">{subtitle}</p>}
      </div>

      <div className="cockpit-topbar-v2 flex-wrap">
        <Link
          to="/ao-vivo"
          className="inline-flex items-center gap-2 rounded-xl border border-white/8 bg-black/25 px-3 py-2 text-sm font-medium text-slate-300 transition-colors hover:border-white/15 hover:text-white"
        >
          <IconArrowLeft className="h-4 w-4" />
          Voltar ao ao vivo
        </Link>

        {activeTab === "qualidade" ? (
          <span className="pill-v2 border border-emerald-400/25 bg-emerald-400/10 text-emerald-300">
            V2 operacional · Superbet #{eventId}
          </span>
        ) : (
          <div className="hidden items-center gap-2 sm:flex">
            <span className="pill-v2 bg-emerald-400 text-slate-950">AO VIVO</span>
          </div>
        )}

        <div className="flex items-center gap-3">
          {activeTab === "qualidade" ? (
            <span className="hidden items-center gap-2 text-xs font-black text-neon-green sm:inline-flex">
              <span className="status-dot-v2" />
              ONLINE
            </span>
          ) : (
            <div className="panel-soft-v2 flex items-center gap-4 px-3 py-1.5">
              <div>
                <p className="text-[9px] font-bold uppercase tracking-wide text-slate-500">Última atualização</p>
                <p className="font-mono text-xs font-black text-white">{fmtTime(data.capturedAt)}</p>
              </div>
              <div className="h-6 w-px bg-white/10" />
              <div>
                <p className="text-[9px] font-bold uppercase tracking-wide text-slate-500">Próxima atualização</p>
                <p className="font-mono text-xs font-black text-white">
                  {isFetching ? "..." : `00:${Math.max(0, Math.ceil((pollFastMs - (secondsSince(data.capturedAt) ?? 0) * 1000) / 1000)).toString().padStart(2, "0")}`}
                </p>
              </div>
            </div>
          )}
          <button
            type="button"
            onClick={onRefresh}
            disabled={isFetching}
            aria-label="Atualizar agora"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-neon-green/25 bg-neon-green/10 text-neon-green transition-colors hover:bg-neon-green/15 disabled:cursor-wait disabled:opacity-60"
          >
            <IconRefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          </button>
          <button
            type="button"
            aria-label="Menu"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-white/8 bg-black/25 text-slate-400 transition-colors hover:text-white"
          >
            <IconMenu className="h-4 w-4" />
          </button>
        </div>
      </div>

      <LiveMatchHeaderV2 data={data} scoreTick={scoreTick} />

      <nav className="tabs-v2 mt-4">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            data-active={activeTab === tab.id}
            onClick={() => onTabChange(tab.id)}
            className="tab-button-v2"
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="mt-5">
        {activeTab === "resumo" && (
          <LiveOperationalSummaryV2
            decision={decision}
            bankroll={bankroll}
            rows={rows}
            history={history}
            data={data}
            quality={quality}
            isAdvicePending={isAdvicePending}
          />
        )}
        {activeTab === "mercados" && <LiveMarketsTableV2 rows={rows} />}
        {activeTab === "qualidade" && (
          <LiveDataQualityV2 data={data} rows={rows} report={quality} onOpenMarkets={() => onTabChange("mercados")} />
        )}
      </div>

      <div className={`v2-update-footer ${isFetching || isAdvicePending ? "pulse" : ""}`}>
        <span>Atualizando odds e recalculando sinais...</span>
        <span>Última atualização: {fmtTime(data.capturedAt)}</span>
      </div>
    </div>
  );
}
