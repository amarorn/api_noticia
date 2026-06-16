import { Link, useLocation, useParams } from "react-router-dom";
import { allNavItems } from "./navConfig";
import { IconChevronRight } from "@/presentation/components/ui/Icons";

interface Crumb {
  label: string;
  to?: string;
}

export function PageBreadcrumb() {
  const { pathname } = useLocation();
  const params = useParams();
  const crumbs = buildCrumbs(pathname, params);

  if (crumbs.length <= 1) return null;

  return (
    <nav aria-label="Breadcrumb" className="mb-3">
      <ol className="flex flex-wrap items-center gap-1 text-[11px] text-slate-500">
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <li key={`${crumb.label}-${i}`} className="flex items-center gap-1">
              {i > 0 && (
                <IconChevronRight className="h-2.5 w-2.5 shrink-0 text-neon-green/20" aria-hidden />
              )}
              {crumb.to && !isLast ? (
                <Link
                  to={crumb.to}
                  className="transition-colors hover:text-neon-green focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-green/40 rounded"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span className={isLast ? "font-medium text-slate-300" : undefined}>
                  {crumb.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function buildCrumbs(
  pathname: string,
  params: Record<string, string | undefined>,
): Crumb[] {
  if (pathname.startsWith("/bilhetes/") && params.home && params.away) {
    const home = decodeURIComponent(params.home);
    const away = decodeURIComponent(params.away);
    return [
      { label: "Dashboard", to: "/" },
      { label: `${home} x ${away}`, to: `/match/${params.home}/${params.away}` },
      { label: "Bilhetes" },
    ];
  }

  if (pathname.startsWith("/match/") && params.home && params.away) {
    const home = decodeURIComponent(params.home);
    const away = decodeURIComponent(params.away);
    return [
      { label: "Dashboard", to: "/" },
      { label: `${home} x ${away}` },
    ];
  }

  if (pathname.startsWith("/album/")) {
    const slug = params.teamSlug ?? "";
    return [
      { label: "Álbum", to: "/album" },
      { label: slug.replace(/-/g, " ") },
    ];
  }

  const item = allNavItems.find((nav) =>
    nav.end ? pathname === nav.to : pathname.startsWith(nav.to) && nav.to !== "/",
  );

  if (pathname === "/") {
    return [{ label: "Dashboard" }];
  }

  if (item) {
    return [{ label: "Início", to: "/" }, { label: item.label }];
  }

  return [{ label: "Início", to: "/" }];
}
