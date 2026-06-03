import { motion } from "framer-motion";

interface BrandMarkProps {
  size?: "sm" | "md";
}

export function BrandMark({ size = "md" }: BrandMarkProps) {
  const dim = size === "sm" ? "h-9 w-9 text-sm" : "h-10 w-10 text-sm";

  return (
    <div className="relative shrink-0">
      <motion.span
        className="absolute inset-0 rounded-xl bg-neon-green/30 blur-md"
        animate={{ opacity: [0.35, 0.65, 0.35], scale: [0.95, 1.05, 0.95] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        aria-hidden
      />
      <motion.div
        whileHover={{ rotate: 180, scale: 1.05 }}
        transition={{ type: "spring", stiffness: 300, damping: 18 }}
        className={`relative flex ${dim} items-center justify-center rounded-xl bg-gradient-to-br from-neon-green via-neon-blue to-neon-purple font-display font-black text-surface shadow-neon ring-1 ring-white/10`}
      >
        AI
      </motion.div>
    </div>
  );
}
