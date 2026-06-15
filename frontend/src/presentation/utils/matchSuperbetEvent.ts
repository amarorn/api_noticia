import type { SuperbetLiveEvent } from "@/domain/entities";

/** Slug canônico PT para cruzar nomes WC ↔ Superbet. */
const TEAM_SLUG: Record<string, string> = {
  brasil: "brasil",
  brazil: "brasil",
  suecia: "suecia",
  sweden: "suecia",
  tunisia: "tunisia",
  tunisie: "tunisia",
  "coreia do sul": "coreia do sul",
  "south korea": "coreia do sul",
  "korea republic": "coreia do sul",
  mexico: "mexico",
  "mexico": "mexico",
  "republica tcheca": "republica tcheca",
  "czech republic": "republica tcheca",
  czechia: "republica tcheca",
  chequia: "republica tcheca",
  holanda: "holanda",
  netherlands: "holanda",
  holland: "holanda",
  "paises baixos": "holanda",
  alemanha: "alemanha",
  germany: "alemanha",
  franca: "franca",
  france: "franca",
  espanha: "espanha",
  spain: "espanha",
  italia: "italia",
  italy: "italia",
  inglaterra: "inglaterra",
  england: "inglaterra",
  argentina: "argentina",
  uruguai: "uruguai",
  uruguay: "uruguai",
  japao: "japao",
  japan: "japao",
  australia: "australia",
  "estados unidos": "estados unidos",
  usa: "estados unidos",
  "united states": "estados unidos",
  "arabia saudita": "arabia saudita",
  "saudi arabia": "arabia saudita",
  marrocos: "marrocos",
  morocco: "marrocos",
  nigeria: "nigeria",
  senegal: "senegal",
  gana: "gana",
  ghana: "gana",
  egito: "egito",
  egypt: "egito",
  "africa do sul": "africa do sul",
  "south africa": "africa do sul",
  argelia: "argelia",
  algeria: "argelia",
  turquia: "turquia",
  turkey: "turquia",
  croacia: "croacia",
  croatia: "croacia",
  belgica: "belgica",
  belgium: "belgica",
  suica: "suica",
  switzerland: "suica",
  austria: "austria",
  dinamarca: "dinamarca",
  denmark: "dinamarca",
  noruega: "noruega",
  norway: "noruega",
  polonia: "polonia",
  poland: "polonia",
  servia: "servia",
  serbia: "servia",
  ucrania: "ucrania",
  ukraine: "ucrania",
  escocia: "escocia",
  scotland: "escocia",
  irlanda: "irlanda",
  ireland: "irlanda",
  ira: "ira",
  iran: "ira",
  catar: "catar",
  qatar: "catar",
  canada: "canada",
  paraguai: "paraguai",
  paraguay: "paraguai",
  equador: "equador",
  ecuador: "equador",
  colombia: "colombia",
  chile: "chile",
  peru: "peru",
  bolivia: "bolivia",
  venezuela: "venezuela",
  "costa do marfim": "costa do marfim",
  "ivory coast": "costa do marfim",
  "cote d ivoire": "costa do marfim",
  cameroon: "camaroes",
  camaroes: "camaroes",
};

function normalizeTeamName(name: string): string {
  return name
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function teamSlug(name: string): string {
  const normalized = normalizeTeamName(name);
  return TEAM_SLUG[normalized] ?? normalized;
}

function teamsMatch(a: string, b: string): boolean {
  const sa = teamSlug(a);
  const sb = teamSlug(b);
  if (!sa || !sb) return false;
  if (sa === sb) return true;
  return sa.includes(sb) || sb.includes(sa);
}

/** Encontra evento Superbet ao vivo pelo par mandante/visitante. */
export function findSuperbetEventForMatch(
  events: SuperbetLiveEvent[] | undefined,
  homeTeam: string,
  awayTeam: string,
): SuperbetLiveEvent | null {
  if (!events?.length) return null;

  for (const event of events) {
    const direct =
      teamsMatch(event.homeTeam, homeTeam) && teamsMatch(event.awayTeam, awayTeam);
    const swapped =
      teamsMatch(event.homeTeam, awayTeam) && teamsMatch(event.awayTeam, homeTeam);
    if (direct || swapped) return event;
  }

  return null;
}

export function buildMatchTicketsPath(homeTeam: string, awayTeam: string): string {
  return `/bilhetes/${encodeURIComponent(homeTeam)}/${encodeURIComponent(awayTeam)}`;
}

export function buildMatchTicketsPathWithEvent(
  homeTeam: string,
  awayTeam: string,
  superbetEventId: number,
): string {
  const base = buildMatchTicketsPath(homeTeam, awayTeam);
  return `${base}?superbetEventId=${superbetEventId}`;
}
