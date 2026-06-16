import { motion } from "framer-motion";

interface BrandMarkProps {
  size?: "sm" | "md" | "lg";
}

export function BrandMark({ size = "md" }: BrandMarkProps) {
  const dims = {
    sm: "h-9 w-9 text-sm",
    md: "h-10 w-10 text-base",
    lg: "h-12 w-12 text-lg",
  };
  const glows = {
    sm: "blur-md",
    md: "blur-lg",
    lg: "blur-xl scale-110",
  };

  return (
    <div className="relative shrink-0">
      <motion.span
        className={`absolute inset-0 rounded-xl bg-neon-green/30 ${glows[size]}`}
        animate={{ opacity: [0.35, 0.65, 0.35], scale: [0.95, 1.05, 0.95] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        aria-hidden
      />
      <motion.div
        whileHover={{ rotate: 180, scale: 1.08 }}
        transition={{ type: "spring", stiffness: 320, damping: 20 }}
        className={`relative flex ${dims[size]} items-center justify-center rounded-xl bg-gradient-to-br from-neon-green via-neon-blue to-neon-purple font-display font-black text-surface shadow-neon ring-1 ring-white/10`}
      >
        <span className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.3)]">AI</span>
      </motion.div>
    </div>
  );
}
