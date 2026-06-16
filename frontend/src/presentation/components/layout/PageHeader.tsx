import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { fadeUpVariants } from "@/presentation/theme/motion";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  /** Alias de subtitle (compatibilidade). */
  description?: string;
  badge?: string;
  badgeColor?: "green" | "blue" | "purple" | "orange";
  children?: ReactNode;
}

const badgeClasses: Record<NonNullable<PageHeaderProps["badgeColor"]>, string> = {
  green: "border-neon-green/25 bg-neon-green/8 text-neon-green",
  blue: "border-neon-blue/25 bg-neon-blue/8 text-neon-blue",
  purple: "border-neon-purple/25 bg-neon-purple/8 text-neon-purple",
  orange: "border-neon-orange/25 bg-neon-orange/8 text-neon-orange",
};

export function PageHeader({
  title,
  subtitle,
  description,
  badge,
  badgeColor = "blue",
  children,
}: PageHeaderProps) {
  const reduced = useReducedMotion();
  const lead = subtitle ?? description;

  return (
    <motion.header
      className="mb-5"
      initial={reduced ? false : "hidden"}
      animate="visible"
      variants={fadeUpVariants}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-xl font-extrabold tracking-tight gradient-text sm:text-2xl">
              {title}
            </h1>
            {badge && (
              <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${badgeClasses[badgeColor]}`}>
                {badge}
              </span>
            )}
          </div>
          {lead && <p className="mt-1 text-xs leading-relaxed text-slate-400">{lead}</p>}
        </div>
        {children}
      </div>
    </motion.header>
  );
}

interface PageHeaderBadge {
  label: string;
  color?: "green" | "blue" | "purple" | "orange";
}

interface HeroPageHeaderProps {
  title: string;
  subtitle: string;
  badges?: PageHeaderBadge[];
  imageSrc?: string;
  imageOpacity?: number;
}

export function HeroPageHeader({
  title,
  subtitle,
  badges,
  imageSrc = "/images/hero-pitch.png",
  imageOpacity = 0.18,
}: HeroPageHeaderProps) {
  const reduced = useReducedMotion();

  return (
    <motion.div
      className="relative mb-5 overflow-hidden rounded-xl border shadow-card"
      style={{
        minHeight: 100,
        borderColor: "rgba(0, 245, 160, 0.10)",
      }}
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      <img
        src={imageSrc}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover object-center"
        style={{ opacity: imageOpacity }}
        draggable={false}
      />
      <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(5,8,17,0.96) 0%, rgba(5,8,17,0.88) 40%, rgba(5,8,17,0.70) 100%)" }} />
      <div className="absolute inset-0 bg-gradient-hero-intense" />
      <div className="divider-glow absolute inset-x-0 top-0" />

      <div className="relative px-4 py-4 sm:px-5 sm:py-5">
        {/* Prompt CLI compacto */}
        <div className="mb-2 flex items-center gap-2">
          <span className="font-mono text-[9px] font-bold tracking-widest" style={{ color: "rgba(0,245,160,0.35)" }}>
            {":: SYSTEM READY"}
          </span>
          <span className="h-px flex-1 bg-gradient-to-r from-neon-green/10 to-transparent" />
        </div>

        <h1 className="font-display text-lg font-extrabold gradient-text-cli sm:text-xl" style={{ textShadow: "0 0 20px rgba(0,245,160,0.10)" }}>
          {title}
        </h1>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-400">{subtitle}</p>
        {badges && badges.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {badges.map((b, i) => (
              <motion.span
                key={b.label}
                initial={reduced ? false : { opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.06 * i }}
                className={`badge-premium ${{
                  green: "border-neon-green/20 text-neon-green",
                  blue: "border-neon-blue/20 text-neon-blue",
                  purple: "border-neon-purple/20 text-neon-purple",
                  orange: "border-neon-orange/20 text-neon-orange",
                }[b.color ?? "blue"]}`}
              >
                {b.label}
              </motion.span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
