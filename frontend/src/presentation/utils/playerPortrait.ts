import type { WcSquad, WcSquadSection, WcSquadPlayer } from "@/domain/entities";

const PLAYER_PORTRAIT: Record<string, string> = {
  Alisson: "/images/player-brasil-1-alisson.png",
  Ederson: "/images/player-brasil-23-ederson.png",
  Danilo: "/images/player-brasil-2-danilo.png",
  Marquinhos: "/images/player-brasil-3-marquinhos.png",
  "Gabriel Magalhães": "/images/player-brasil-4-gabriel.png",
  "Alex Telles": "/images/player-brasil-12-telles.png",
  Casemiro: "/images/player-brasil-5-casemiro.png",
  Fred: "/images/player-brasil-8-fred.png",
  "Lucas Paquetá": "/images/player-brasil-10-paqueta.png",
  Rodrygo: "/images/player-brasil-7-rodrygo.png",
  Raphinha: "/images/player-brasil-11-raphinha.png",
  "Vinicius Jr": "/images/player-brasil-20-vinicius.png",
  Richarlison: "/images/player-brasil-9-richarlison.png",
  Endrick: "/images/player-brasil-18-endrick.png",
};

const TEAM_PORTRAIT: Record<string, string> = {
  Brasil: "/images/player-brasil.png",
  Argentina: "/images/player-argentina.png",
  França: "/images/player-franca.png",
  Espanha: "/images/player-espanha.png",
  Alemanha: "/images/player-alemanha.png",
  Inglaterra: "/images/player-brasil.png",
  Portugal: "/images/player-portugal.png",
  Itália: "/images/player-italia.png",
  Holanda: "/images/player-holanda.png",
  Croácia: "/images/player-croacia.png",
  Marrocos: "/images/player-marrocos.png",
  Japão: "/images/player-japao.png",
  México: "/images/player-mexico.png",
  Senegal: "/images/player-marrocos.png",
  Colômbia: "/images/player-mexico.png",
  Uruguai: "/images/player-argentina.png",
  Bélgica: "/images/player-franca.png",
  Suécia: "/images/player-alemanha.png",
  Dinamarca: "/images/player-alemanha.png",
  Austrália: "/images/player-brasil.png",
  Suíça: "/images/player-espanha.png",
  Canadá: "/images/player-brasil.png",
  "Estados Unidos": "/images/player-brasil.png",
  "Coreia do Sul": "/images/player-japao.png",
  "República Tcheca": "/images/player-espanha.png",
  Bósnia: "/images/player-croacia.png",
  Catar: "/images/player-marrocos.png",
  "África do Sul": "/images/player-marrocos.png",
  Turquia: "/images/player-italia.png",
};

export function resolvePlayerPortrait(playerName: string, teamName: string): string {
  return (
    PLAYER_PORTRAIT[playerName] ??
    TEAM_PORTRAIT[teamName] ??
    "/images/player-brasil.png"
  );
}

export function shortPlayerName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length <= 1) return fullName;
  if (parts.length === 2) return parts[parts.length - 1];
  return `${parts[0][0]}. ${parts[parts.length - 1]}`;
}

export type NumberedSquadPlayer = WcSquadPlayer & { number: number };

export type NumberedWcSquadSection = Omit<WcSquadSection, "players"> & {
  players: NumberedSquadPlayer[];
};

export function assignSquadNumbers(
  squad: WcSquad,
): { sections: NumberedWcSquadSection[]; players: NumberedSquadPlayer[] } {
  let number = 1;
  const players: NumberedSquadPlayer[] = [];
  const sections = squad.sections.map((section) => ({
    ...section,
    players: section.players.map((player) => {
      const numbered = { ...player, number: number++ };
      players.push(numbered);
      return numbered;
    }),
  }));
  return { sections, players };
}
