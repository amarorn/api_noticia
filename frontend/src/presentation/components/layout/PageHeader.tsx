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
      className="mb-8"
      initial={reduced ? false : "hidden"}
      animate="visible"
      variants={fadeUpVariants}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-2xl font-extrabold tracking-tight gradient-text sm:text-3xl">
              {title}
            </h1>
            {badge && (
              <span
                className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${badgeClasses[badgeColor]}`}
              >
                {badge}
              </span>
            )}
          </div>
          {lead && <p className="mt-1.5 text-sm text-slate-400">{lead}</p>}
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
  imageOpacity = 0.22,
}: HeroPageHeaderProps) {
  const reduced = useReducedMotion();

  return (
    <motion.div
      className="relative mb-8 overflow-hidden rounded-2xl border shadow-card-deep"
      style={{
        minHeight: 160,
        borderColor: "rgba(0, 245, 160, 0.10)",
      }}
      initial={reduced ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      <img
        src={imageSrc}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 h-full w-full object-cover object-center"
        style={{ opacity: imageOpacity }}
        draggable={false}
      />
      <div className="absolute inset-0" style={{ background: "linear-gradient(180deg, rgba(5,8,17,0.97) 0%, rgba(5,8,17,0.85) 50%, rgba(5,8,17,0.70) 100%)" }} />
      <div className="absolute inset-0 bg-gradient-hero-intense" />
      <div className="divider-glow absolute inset-x-0 top-0" />

      {/* Cantos decorativos CLI */}
      <div className="absolute left-2 top-2 h-5 w-5 border-l-2 border-t-2 border-neon-green/20 rounded-tl" />
      <div className="absolute right-2 top-2 h-5 w-5 border-r-2 border-t-2 border-neon-blue/20 rounded-tr" />
      <div className="absolute left-2 bottom-2 h-5 w-5 border-l-2 border-b-2 border-neon-purple/20 rounded-bl" />
      <div className="absolute right-2 bottom-2 h-5 w-5 border-r-2 border-b-2 border-neon-pink/20 rounded-br" />

      <div className="relative p-6 sm:p-8">
        {/* Prompt CLI */}
        <div className="mb-3 flex items-center gap-2">
          <span className="font-mono text-[10px] font-bold tracking-widest" style={{ color: "rgba(0,245,160,0.4)" }}>
            {":: SYSTEM READY"}
          </span>
          <span className="h-px flex-1 bg-gradient-to-r from-neon-green/15 to-transparent" />
        </div>

        <h1 className="font-display text-2xl font-extrabold gradient-text-cli sm:text-3xl" style={{ textShadow: "0 0 30px rgba(0,245,160,0.15)" }}>
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">{subtitle}</p>
        {badges && badges.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {badges.map((b, i) => (
              <motion.span
                key={b.label}
                initial={reduced ? false : { opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.08 * i }}
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
