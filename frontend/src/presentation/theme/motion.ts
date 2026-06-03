import type { Transition, Variants } from "framer-motion";

export const springSnappy: Transition = {
  type: "spring",
  stiffness: 420,
  damping: 32,
  mass: 0.8,
};

export const springSoft: Transition = {
  type: "spring",
  stiffness: 260,
  damping: 28,
};

export const easeOutExpo = [0.22, 1, 0.36, 1] as const;

export const pageVariants: Variants = {
  initial: { opacity: 0, y: 16, filter: "blur(6px)" },
  animate: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.38, ease: easeOutExpo },
  },
  exit: {
    opacity: 0,
    y: -10,
    filter: "blur(4px)",
    transition: { duration: 0.22, ease: easeOutExpo },
  },
};

export const pageVariantsReduced: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.15 } },
  exit: { opacity: 0, transition: { duration: 0.1 } },
};

export const staggerContainerVariants: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06, delayChildren: 0.04 } },
};

export const staggerItemVariants: Variants = {
  hidden: { opacity: 0, y: 20, scale: 0.98 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: springSoft,
  },
};

export const fadeUpVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35, ease: easeOutExpo } },
};
