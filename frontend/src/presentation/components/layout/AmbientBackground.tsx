import { motion } from "framer-motion";

export function AmbientBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden>
      {/* Mesh principal com 3 cores de marca */}
      <div className="ambient-mesh absolute inset-0" />

      {/* Grade sutil */}
      <div className="ambient-grid absolute inset-0 opacity-[0.35]" />

      {/* Faixa superior luminosa */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neon-green/20 to-transparent" />

      {/* Orbes decorativos com movimentos variados */}
      <motion.div
        className="ambient-orb absolute -left-28 top-0 h-[30rem] w-[30rem] rounded-full bg-neon-purple/12 blur-3xl"
        animate={{ x: [0, 50, 0], y: [0, 35, 0], scale: [1, 1.10, 1] }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="ambient-orb absolute -right-24 top-1/4 h-[28rem] w-[28rem] rounded-full bg-neon-blue/10 blur-3xl"
        animate={{ x: [0, -40, 0], y: [0, 50, 0], scale: [1, 1.08, 1] }}
        transition={{ duration: 24, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="ambient-orb absolute bottom-0 left-1/3 h-80 w-80 rounded-full bg-neon-green/10 blur-3xl"
        animate={{ x: [0, 30, 0], y: [0, -25, 0], scale: [1, 1.12, 1] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="ambient-orb absolute right-1/4 bottom-1/3 h-64 w-64 rounded-full bg-neon-pink/8 blur-[80px]"
        animate={{ x: [0, -20, 0], y: [0, 20, 0], scale: [1, 1.06, 1] }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Estrelas / pontos de luz sutil */}
      <div className="absolute inset-0 opacity-[0.12]" style={{
        backgroundImage: `radial-gradient(circle at 20% 20%, rgba(0,255,136,0.4) 0px, transparent 1.5px),
                          radial-gradient(circle at 80% 10%, rgba(0,212,255,0.4) 0px, transparent 1.5px),
                          radial-gradient(circle at 40% 80%, rgba(168,85,247,0.4) 0px, transparent 1.5px),
                          radial-gradient(circle at 10% 60%, rgba(0,212,255,0.3) 0px, transparent 1.5px),
                          radial-gradient(circle at 90% 50%, rgba(0,255,136,0.3) 0px, transparent 1.5px)`,
        backgroundSize: '300px 300px, 400px 400px, 350px 350px, 450px 450px, 380px 380px',
      }} />
    </div>
  );
}
