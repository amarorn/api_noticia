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
    sm: "blur-lg",
    md: "blur-xl",
    lg: "blur-2xl",
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
        whileHover={{ rotate: 180, scale: 1.1 }}
        transition={{ type: "spring", stiffness: 320, damping: 18 }}
        className={`relative flex ${dims[size]} items-center justify-center rounded-xl font-display font-black shadow-neon ring-1 ring-white/10`}
        style={{
          background: "linear-gradient(135deg, #00f5a0, #00e0ff, #c084fc)",
          color: "#050811",
        }}
      >
        <span className="drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]">AI</span>
      </motion.div>
    </div>
  );
}
