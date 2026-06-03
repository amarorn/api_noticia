const TEAM_ISO: Record<string, string> = {
  Alemanha: "DE",
  "Alemanha Oriental": "DE",
  Argentina: "AR",
  Argélia: "DZ",
  Austrália: "AU",
  Áustria: "AT",
  Bélgica: "BE",
  Bolívia: "BO",
  Bósnia: "BA",
  "Bósnia e Herzegovina": "BA",
  Catar: "QA",
  Qatar: "QA",
  Brasil: "BR",
  Bulgária: "BG",
  Camarões: "CM",
  Canadá: "CA",
  Chile: "CL",
  China: "CN",
  Colômbia: "CO",
  "Coreia do Norte": "KP",
  "Coreia do Sul": "KR",
  "Costa do Marfim": "CI",
  "Costa Rica": "CR",
  Croácia: "HR",
  Dinamarca: "DK",
  Egito: "EG",
  Equador: "EC",
  Escócia: "GB",
  Espanha: "ES",
  "Estados Unidos": "US",
  Finlândia: "FI",
  França: "FR",
  Gana: "GH",
  Grécia: "GR",
  Holanda: "NL",
  Honduras: "HN",
  Hungria: "HU",
  Inglaterra: "GB",
  Irã: "IR",
  Irlanda: "IE",
  "Irlanda do Norte": "GB",
  Islândia: "IS",
  Itália: "IT",
  Iugoslávia: "RS",
  Jamaica: "JM",
  Japão: "JP",
  Marrocos: "MA",
  México: "MX",
  Nigéria: "NG",
  Noruega: "NO",
  Panamá: "PA",
  Paraguai: "PY",
  Peru: "PE",
  Polônia: "PL",
  Portugal: "PT",
  Romênia: "RO",
  Rússia: "RU",
  Senegal: "SN",
  Sérvia: "RS",
  Suíça: "CH",
  Suécia: "SE",
  Tchecoslováquia: "CZ",
  "República Tcheca": "CZ",
  Tunísia: "TN",
  Turquia: "TR",
  URSS: "RU",
  Ucrânia: "UA",
  Uruguai: "UY",
  Venezuela: "VE",
  "África do Sul": "ZA",
  "Arábia Saudita": "SA",
  "Emirados Árabes": "AE",
  "País de Gales": "GB",
  Eslováquia: "SK",
  Eslovênia: "SI",
  "Cabo Verde": "CV",
};

function isoToFlag(iso: string): string {
  return iso
    .toUpperCase()
    .split("")
    .map((char) => String.fromCodePoint(127397 + char.charCodeAt(0)))
    .join("");
}

export function getTeamIso(teamName: string): string | null {
  return TEAM_ISO[teamName] ?? null;
}

export function teamFlagImageUrl(teamName: string, width = 40): string | null {
  const iso = getTeamIso(teamName);
  if (!iso) return null;
  const w = width <= 40 ? 40 : width <= 80 ? 80 : 160;
  return `https://flagcdn.com/w${w}/${iso.toLowerCase()}.png`;
}

export function teamFlag(teamName: string): string {
  const iso = TEAM_ISO[teamName];
  return iso ? isoToFlag(iso) : "🏳️";
}

export function formatMatchDate(isoDate: string): string {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}
