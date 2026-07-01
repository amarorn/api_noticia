import { motion } from "framer-motion";

export function AmbientBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden>
      {/* Mesh principal */}
      <div className="ambient-mesh absolute inset-0" />

      {/* Grid neon */}
      <div className="ambient-grid absolute inset-0 opacity-[0.40]" />

      {/* Faixa superior CLI */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neon-green/30 to-transparent" />

      {/* Scanline bar -- barra de scanner vertical que desce lentamente */}
      <motion.div
        className="absolute left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-neon-green/20 to-transparent"
        animate={{ top: ["-10%", "110%"] }}
        transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
      />

      {/* Orbes decorativos com cores CLI */}
      <motion.div
        className="ambient-orb absolute -left-28 top-0 h-[30rem] w-[30rem] rounded-full blur-3xl"
        style={{ background: "rgba(192, 132, 252, 0.12)" }}
        animate={{ x: [0, 50, 0], y: [0, 35, 0], scale: [1, 1.10, 1] }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="ambient-orb absolute -right-24 top-1/4 h-[28rem] w-[28rem] rounded-full blur-3xl"
        style={{ background: "rgba(0, 224, 255, 0.10)" }}
        animate={{ x: [0, -40, 0], y: [0, 50, 0], scale: [1, 1.08, 1] }}
        transition={{ duration: 24, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="ambient-orb absolute bottom-0 left-1/3 h-80 w-80 rounded-full blur-3xl"
        style={{ background: "rgba(0, 245, 160, 0.10)" }}
        animate={{ x: [0, 30, 0], y: [0, -25, 0], scale: [1, 1.12, 1] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="ambient-orb absolute right-1/4 bottom-1/3 h-72 w-72 rounded-full blur-[80px]"
        style={{ background: "rgba(255, 107, 157, 0.08)" }}
        animate={{ x: [0, -20, 0], y: [0, 20, 0], scale: [1, 1.06, 1] }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="ambient-orb absolute top-1/2 left-1/2 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full blur-[100px]"
        style={{ background: "rgba(255, 159, 67, 0.05)" }}
        animate={{ scale: [1, 1.15, 1], opacity: [0.4, 0.7, 0.4] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Estrelas / pontos de luz sutil */}
      <div
        className="absolute inset-0 opacity-[0.15]"
        style={{
          backgroundImage: `
            radial-gradient(circle at 20% 20%, rgba(0,245,160,0.5) 0px, transparent 1.5px),
            radial-gradient(circle at 80% 10%, rgba(0,224,255,0.5) 0px, transparent 1.5px),
            radial-gradient(circle at 40% 80%, rgba(192,132,252,0.5) 0px, transparent 1.5px),
            radial-gradient(circle at 10% 60%, rgba(0,224,255,0.4) 0px, transparent 1.5px),
            radial-gradient(circle at 90% 50%, rgba(0,245,160,0.4) 0px, transparent 1.5px),
            radial-gradient(circle at 60% 30%, rgba(255,107,157,0.3) 0px, transparent 1.5px)
          `,
          backgroundSize: "300px 300px, 400px 400px, 350px 350px, 450px 450px, 380px 380px, 480px 480px",
        }}
      />

      {/* Cantos decorativos CLI */}
      <div className="absolute left-2 top-2 h-6 w-6 border-l-2 border-t-2 border-neon-green/20 rounded-tl-md" />
      <div className="absolute right-2 top-2 h-6 w-6 border-r-2 border-t-2 border-neon-blue/20 rounded-tr-md" />
      <div className="absolute left-2 bottom-2 h-6 w-6 border-l-2 border-b-2 border-neon-purple/20 rounded-bl-md" />
      <div className="absolute right-2 bottom-2 h-6 w-6 border-r-2 border-b-2 border-neon-pink/20 rounded-br-md" />
    </div>
  );
}
