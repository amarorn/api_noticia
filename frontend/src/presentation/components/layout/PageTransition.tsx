import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import {
  staggerContainerVariants,
  staggerItemVariants,
} from "@/presentation/theme/motion";

interface PageTransitionProps {
  children: ReactNode;
  className?: string;
  /** Dashboard ao vivo — sem padding automático (layout próprio). */
  live?: boolean;
}

export function PageTransition({ children, className, live }: PageTransitionProps) {
  const shell = live ? "app-page-shell app-page-shell--live" : "app-page-shell";
  return <div className={className ? `${shell} ${className}` : shell}>{children}</div>;
}

export function StaggerContainer({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const reduced = useReducedMotion();

  if (reduced) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={staggerContainerVariants}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const reduced = useReducedMotion();

  if (reduced) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div variants={staggerItemVariants} className={className}>
      {children}
    </motion.div>
  );
}
