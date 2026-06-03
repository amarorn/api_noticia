import { getTeamIso } from "@/presentation/utils/teamFlags";
import { teamColor } from "@/data/teamColors";

const FLAG_CDN = "https://flagcdn.com";

type TeamFlagProps = {
  team: string;
  size?: number;
  className?: string;
  rounded?: "md" | "full";
};

export function TeamFlag({
  team,
  size = 32,
  className = "",
  rounded = "full",
}: TeamFlagProps) {
  const iso = getTeamIso(team);
  const radius = rounded === "full" ? "rounded-full" : "rounded-md";

  if (!iso) {
    const color = teamColor(team);
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center text-sm font-bold text-white ${radius} ${className}`}
        style={{ width: size, height: size, backgroundColor: color }}
        aria-hidden
        title={team}
      >
        {team.slice(0, 2).toUpperCase()}
      </span>
    );
  }

  const width = size <= 40 ? 40 : size <= 80 ? 80 : 160;

  return (
    <img
      src={`${FLAG_CDN}/w${width}/${iso.toLowerCase()}.png`}
      srcSet={`${FLAG_CDN}/w${width}/${iso.toLowerCase()}.png 1x, ${FLAG_CDN}/w${Math.min(width * 2, 160)}/${iso.toLowerCase()}.png 2x`}
      width={size}
      height={Math.round(size * 0.67)}
      alt={`Bandeira ${team}`}
      title={team}
      loading="lazy"
      decoding="async"
      className={`shrink-0 object-cover shadow-sm ring-1 ring-white/10 ${radius} ${className}`}
      style={{ width: size, height: size, objectFit: "cover" }}
    />
  );
}
