/** Regras de gamificação do álbum — figurinhas liberadas por ações do usuário. */
const REWARDS_KEY = "wc2026_album_rewards";
const EVENTS_KEY = "wc2026_album_reward_events";

export type AlbumRewardReason =
  | "first_prediction"
  | "correct_result"
  | "round_complete"
  | "win_streak";

export interface AlbumRewardEvent {
  id: string;
  reason: AlbumRewardReason;
  team?: string;
  at: string;
  label: string;
}

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key: string, value: unknown) {
  localStorage.setItem(key, JSON.stringify(value));
}

export function getUnlockedTeams(): Set<string> {
  return new Set(loadJson<string[]>(REWARDS_KEY, []));
}

export function getRewardEvents(): AlbumRewardEvent[] {
  return loadJson<AlbumRewardEvent[]>(EVENTS_KEY, []);
}

export function unlockTeamSticker(team: string, reason: AlbumRewardEvent): boolean {
  const set = getUnlockedTeams();
  if (set.has(team)) return false;
  set.add(team);
  saveJson(REWARDS_KEY, [...set]);
  const events = getRewardEvents();
  events.unshift(reason);
  saveJson(EVENTS_KEY, events.slice(0, 50));
  return true;
}

export function recordAlbumReward(
  team: string,
  reason: AlbumRewardReason,
  label: string,
): boolean {
  return unlockTeamSticker(team, {
    id: `${reason}-${team}-${Date.now()}`,
    reason,
    team,
    at: new Date().toISOString(),
    label,
  });
}

export const REWARD_COPY: Record<AlbumRewardReason, string> = {
  first_prediction: "Faça um palpite em qualquer jogo para desbloquear a figurinha da seleção.",
  correct_result: "Acerte o resultado (1/X/2) para ganhar a figurinha do time.",
  round_complete: "Complete todos os palpites de uma rodada para liberar extras.",
  win_streak: "Acerte 3 palpites seguidos para ganhar figurinha especial.",
};

export function albumProgress(collected: Set<string>, totalTeams: number) {
  const pct = totalTeams > 0 ? Math.round((collected.size / totalTeams) * 100) : 0;
  return { collected: collected.size, total: totalTeams, pct };
}
