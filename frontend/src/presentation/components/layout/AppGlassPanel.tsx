import type { ReactNode } from "react";

type AppGlassPanelVariant = "default" | "glow" | "elevated";

interface AppGlassPanelProps {
  children: ReactNode;
  className?: string;
  variant?: AppGlassPanelVariant;
  as?: "div" | "section" | "article";
}

const variantClass: Record<AppGlassPanelVariant, string> = {
  default: "live-glass-panel",
  glow: "live-glass-panel-glow glow-border",
  elevated: "glass-card-elevated",
};

export function AppGlassPanel({
  children,
  className = "",
  variant = "default",
  as: Tag = "div",
}: AppGlassPanelProps) {
  return <Tag className={`${variantClass[variant]} ${className}`.trim()}>{children}</Tag>;
}
