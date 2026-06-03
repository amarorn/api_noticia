import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { fadeUpVariants } from "@/presentation/theme/motion";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
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
  badge,
  badgeColor = "blue",
  children,
}: PageHeaderProps) {
  const reduced = useReducedMotion();

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
          {subtitle && <p className="mt-1.5 text-sm text-slate-400">{subtitle}</p>}
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
  imageOpacity = 0.28,
}: HeroPageHeaderProps) {
  const reduced = useReducedMotion();

  return (
    <motion.div
      className="relative mb-8 overflow-hidden rounded-2xl border border-white/[0.08] shadow-card"
      style={{ minHeight: 160 }}
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
      <div className="absolute inset-0 bg-gradient-to-r from-surface/96 via-surface/82 to-surface/45" />
      <div className="absolute inset-0 bg-gradient-hero" />
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neon-green/30 to-transparent" />

      <div className="relative p-6 sm:p-8">
        <h1 className="font-display text-2xl font-extrabold gradient-text-animated sm:text-3xl">
          {title}
        </h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-slate-400">{subtitle}</p>
        {badges && badges.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {badges.map((b, i) => (
              <motion.span
                key={b.label}
                initial={reduced ? false : { opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.08 * i }}
                className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${badgeClasses[b.color ?? "blue"]}`}
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
