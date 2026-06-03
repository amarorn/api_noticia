import type { MatchContextView, PreMatchTeamStats, WcPrediction } from "@/domain/entities";

function parsePercent(text: string): number | undefined {
  const m = text.match(/([\d.]+)\s*%/);
  return m ? parseFloat(m[1]) / 100 : undefined;
}

function parseTeamBlock(body: string): PreMatchTeamStats | null {
  const elo = body.match(/Elo:\s*([\d.]+)/i);
  const goals = body.match(/Gols\/jogo:\s*([\d.]+)/i);
  const conceded = body.match(/Sofridos\/jogo:\s*([\d.]+)/i);
  const form = body.match(/Forma recente:\s*(.+)/i);
  if (!elo) return null;
  return {
    elo: parseFloat(elo[1]),
    goalsPerGame: goals ? parseFloat(goals[1]) : 0,
    concededPerGame: conceded ? parseFloat(conceded[1]) : 0,
    form: form?.[1]?.trim() ?? "—",
  };
}

function parseKxlTeam(body: string) {
  const attack = body.match(/Ataque:\s*([\d.]+)/i);
  const defense = body.match(/Defesa:\s*([\d.]+)/i);
  const control = body.match(/Controle:\s*([\d.]+)/i);
  if (!attack) return null;
  return {
    attack: parseFloat(attack[1]),
    defense: defense ? parseFloat(defense[1]) : 0,
    control: control ? parseFloat(control[1]) : 0,
    shots: (() => {
      const m = body.match(/Chutes\/jogo:\s*([\d.]+)/i);
      return m ? parseFloat(m[1]) : undefined;
    })(),
    possession: (() => {
      const m = body.match(/Posse:\s*([\d.]+%?)/i);
      return m ? parsePercent(m[1]) : undefined;
    })(),
    counter: (() => {
      const m = body.match(/Contra-ataque:\s*([\d.]+)/i);
      return m ? parseFloat(m[1]) : undefined;
    })(),
    gkWeakness: (() => {
      const m = body.match(/Fraqueza GK dentro da área:\s*([\d.]+%?)/i);
      return m ? parsePercent(m[1]) : undefined;
    })(),
  };
}

export function parseMatchContextFromMarkdown(
  context: string,
  homeTeam: string,
  awayTeam: string,
): MatchContextView {
  const sections = context.split(/^## /m).filter(Boolean);
  let preMatch: MatchContextView["preMatch"] = null;
  let kxlProfile: MatchContextView["kxlProfile"] = null;

  for (const raw of sections) {
    const titleLine = raw.split("\n")[0]?.trim() ?? "";
    const body = raw.slice(raw.indexOf("\n") + 1);

    if (titleLine.includes("Estatísticas pré-jogo")) {
      const teams = [...body.matchAll(/^### (.+)$/gm)];
      const h2h = body.match(
        /Vitórias ([^:]+):\s*(\d+).*Empates:\s*(\d+).*Vitórias ([^:]+):\s*(\d+)/,
      );
      const homeBlock = teams.find((t) => t[1].trim() === homeTeam);
      const awayBlock = teams.find((t) => t[1].trim() === awayTeam);
      if (homeBlock && awayBlock) {
        const homeStart = homeBlock.index!;
        const awayStart = awayBlock.index!;
        const homeBody = body.slice(homeStart, awayStart);
        const awayBody = body.slice(awayStart);
        const homeStats = parseTeamBlock(homeBody);
        const awayStats = parseTeamBlock(awayBody);
        if (homeStats && awayStats) {
          preMatch = {
            home: homeStats,
            away: awayStats,
            h2h: {
              homeWins: h2h ? parseInt(h2h[2], 10) : 0,
              draws: h2h ? parseInt(h2h[3], 10) : 0,
              awayWins: h2h ? parseInt(h2h[5], 10) : 0,
              total: h2h
                ? parseInt(h2h[2], 10) + parseInt(h2h[3], 10) + parseInt(h2h[5], 10)
                : 0,
            },
          };
        }
      }
    }

    if (titleLine.includes("Perfil tático KXL")) {
      const teams = [...body.matchAll(/^### (.+)$/gm)];
      const homeBlock = teams.find((t) => t[1].trim() === homeTeam);
      const awayBlock = teams.find((t) => t[1].trim() === awayTeam);
      const sectorNote = body.match(/^- (.+vantagem.+)$/m)?.[1];
      const pressure = body.match(
        /Pressão ofensiva .+?:\s*([\d.]+)\s*\|\s*.+?:\s*([\d.]+)/,
      );
      const probs = body.match(
        /Palpite vetorial[^:]*:\s*1=(\d+)%\s*X=(\d+)%\s*2=(\d+)%/,
      );
      if (homeBlock && awayBlock) {
        const homeStart = homeBlock.index!;
        const awayStart = awayBlock.index!;
        const homeBody = body.slice(homeStart, awayStart);
        const awayBody = body.slice(awayStart, body.indexOf("### Matchup"));
        const homeKxl = parseKxlTeam(homeBody);
        const awayKxl = parseKxlTeam(awayBody);
        if (homeKxl && awayKxl) {
          kxlProfile = {
            home: homeKxl,
            away: awayKxl,
            sectorNote: sectorNote ?? "",
            pressureHome: pressure ? parseFloat(pressure[1]) : 0,
            pressureAway: pressure ? parseFloat(pressure[2]) : 0,
            probHome: probs ? parseInt(probs[1], 10) / 100 : 0,
            probDraw: probs ? parseInt(probs[2], 10) / 100 : 0,
            probAway: probs ? parseInt(probs[3], 10) / 100 : 0,
          };
        }
      }
    }
  }

  return { preMatch, kxlProfile };
}

export function buildMatchContextView(prediction: WcPrediction): MatchContextView {
  return parseMatchContextFromMarkdown(
    prediction.context,
    prediction.homeTeam,
    prediction.awayTeam,
  );
}
