import { Link, useLocation } from "react-router-dom";
import { HexBrandMark } from "./HexBrandMark";
import { LIVE_TOPBAR_HEIGHT_PX } from "@/presentation/components/layout/liveDashboardChromeContext";
import { NotificationBell } from "@/presentation/components/ui/notifications";

interface LiveDashboardTopBarProps {
  isLive: boolean;
  lastUpdate: string;
  nextUpdate: string;
  isFetching: boolean;
  onRefresh: () => void;
  onMenu?: () => void;
}

function TopBarDivider() {
  return <div className="hidden h-9 w-px shrink-0 bg-white/10 sm:block" aria-hidden />;
}

export function LiveDashboardTopBar({
  isLive,
  lastUpdate,
  nextUpdate,
  isFetching,
  onRefresh,
  onMenu,
}: LiveDashboardTopBarProps) {
  const location = useLocation();
  const isBasket = location.pathname.includes("/ao-vivo/basquete/");

  return (
    <header
      className="live-unified-chrome relative z-50 flex w-full shrink-0 items-center justify-between gap-3 border-b border-white/[0.06] px-3 sm:gap-4 sm:px-5"
      style={{
        minHeight: LIVE_TOPBAR_HEIGHT_PX,
        boxShadow: "inset 0 1px 0 rgba(0,224,255,0.10)",
      }}
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neon-blue/50 to-transparent"
        aria-hidden
      />

      <Link
        to="/"
        className="flex min-w-0 items-center gap-2.5 rounded-lg transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-green/40 sm:gap-3"
      >
        <HexBrandMark size="sm" />
        <div className="min-w-0">
          <p className="truncate font-display text-sm font-bold leading-tight text-white sm:text-base">
            Bolão AI
          </p>
          <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-slate-500 sm:text-[10px]">
            {isBasket ? "Basquete NBA" : "Campeonatos"}
          </p>
        </div>
      </Link>

      <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        {isLive && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-neon-green/35 bg-neon-green/[0.08] px-2.5 py-1 text-[9px] font-bold uppercase tracking-[0.14em] text-neon-green shadow-[0_0_16px_rgba(0,245,160,0.12)] sm:text-[10px]">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-neon-green shadow-[0_0_6px_rgba(0,245,160,0.9)]" />
            Ao vivo
          </span>
        )}

        <TopBarDivider />

        <div className="hidden items-center gap-4 md:flex">
          <div className="text-right leading-tight">
            <p className="text-[9px] uppercase tracking-wider text-slate-500">Última atualização</p>
            <p className="font-mono text-xs font-semibold tabular-nums text-white">{lastUpdate}</p>
          </div>

          <TopBarDivider />

          <div className="text-right leading-tight">
            <p className="text-[9px] uppercase tracking-wider text-slate-500">Próxima atualização</p>
            <p className="font-mono text-xs font-semibold tabular-nums text-white">{nextUpdate}</p>
          </div>
        </div>

        <TopBarDivider />

        <NotificationBell />

        <button
          type="button"
          onClick={onRefresh}
          disabled={isFetching}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300 transition hover:border-neon-green/35 hover:text-neon-green disabled:opacity-50"
          title="Atualizar"
          aria-label="Atualizar"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`}
          >
            <path
              fillRule="evenodd"
              d="M15.312 11.424a5.5 5.5 0 0 1-9.201 2.466l-.312-.311h2.433a.75.75 0 0 0 0-1.5H3.989a.75.75 0 0 0-.75.75v4.242a.75.75 0 0 0 1.5 0v-2.43l.31.31a7 7 0 0 0 11.712-3.138.75.75 0 0 0-1.46-.33Zm-7.66-8.848A5.5 5.5 0 0 1 18.5 10a.75.75 0 0 0 1.5 0 7 7 0 0 0-11.712-5.138l-.31.31V2.75a.75.75 0 0 0-1.5 0v4.243c0 .414.336.75.75.75h4.243a.75.75 0 0 0 0-1.5h-2.43l.31-.31Z"
              clipRule="evenodd"
            />
          </svg>
        </button>

        <button
          type="button"
          onClick={onMenu}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-300 transition hover:border-white/20 hover:text-white"
          aria-label="Menu"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            className="h-4 w-4"
          >
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
      </div>
    </header>
  );
}
