import { motion } from "framer-motion";

export function AmbientBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden>
      <div className="ambient-mesh absolute inset-0" />
      <div className="ambient-grid absolute inset-0 opacity-[0.35]" />

      <motion.div
        className="ambient-orb absolute -left-24 top-0 h-[28rem] w-[28rem] rounded-full bg-neon-purple/12 blur-3xl"
        animate={{ x: [0, 40, 0], y: [0, 30, 0], scale: [1, 1.08, 1] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="ambient-orb absolute -right-24 top-1/4 h-[26rem] w-[26rem] rounded-full bg-neon-blue/10 blur-3xl"
        animate={{ x: [0, -35, 0], y: [0, 45, 0], scale: [1, 1.06, 1] }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="ambient-orb absolute bottom-0 left-1/3 h-72 w-72 rounded-full bg-neon-green/10 blur-3xl"
        animate={{ x: [0, 25, 0], y: [0, -20, 0], scale: [1, 1.1, 1] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />

      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neon-green/20 to-transparent" />
    </div>
  );
}
