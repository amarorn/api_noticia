/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        display: ['"Space Grotesk"', "Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "1rem" }],
        "3xs": ["0.55rem", { lineHeight: "0.85rem" }],
      },
      letterSpacing: {
        micro: "0.08em",
      },
      colors: {
        // ── Cyberpunk / CLI Neon ───────────────────────────────
        neon: {
          green: "#00f5a0",
          "green-dark": "#00c27d",
          blue: "#00e0ff",
          "blue-dark": "#00a8cc",
          purple: "#c084fc",
          "purple-dark": "#a855f7",
          pink: "#ff6b9d",
          "pink-dark": "#e84880",
          orange: "#ff9f43",
          yellow: "#ffd166",
          red: "#ff4d6d",
          cyan: "#00f5e1",
          magenta: "#ff00ff",
        },
        // ── Surface Profundo ───────────────────────────────────
        surface: {
          DEFAULT: "#050811",
          50: "#080d18",
          100: "#0a1020",
          200: "#0e1528",
          300: "#121b32",
          400: "#16203c",
          card: "rgba(10, 16, 32, 0.82)",
          elevated: "rgba(18, 27, 50, 0.72)",
          border: "rgba(0, 245, 160, 0.12)",
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        // Fundo base mais escuro e profundo
        "mesh-gradient":
          "linear-gradient(175deg, #03050b 0%, #070b14 40%, #0a0f1c 100%)",
        "mesh-gradient-cli":
          "linear-gradient(180deg, #04060b 0%, #060913 50%, #080d18 100%)",
        // Gradiente hero com neons mais saturados
        "gradient-hero":
          "linear-gradient(135deg, rgba(0,245,160,0.08) 0%, rgba(0,224,255,0.06) 50%, rgba(192,132,252,0.07) 100%)",
        "gradient-hero-intense":
          "linear-gradient(135deg, rgba(0,245,160,0.12) 0%, rgba(0,224,255,0.10) 50%, rgba(192,132,252,0.12) 100%)",
        // Gradiente de marca CLI
        "brand-gradient":
          "linear-gradient(120deg, #00f5a0 0%, #00e0ff 40%, #c084fc 70%, #ff6b9d 100%)",
        "brand-gradient-subtle":
          "linear-gradient(120deg, rgba(0,245,160,0.15) 0%, rgba(0,224,255,0.12) 40%, rgba(192,132,252,0.15) 100%)",
        // Aurora
        "aurora-gradient":
          "linear-gradient(180deg, rgba(0,245,160,0.04) 0%, rgba(0,224,255,0.03) 50%, rgba(192,132,252,0.04) 100%)",
        // Scanlines CLI
        "scanline":
          "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 245, 160, 0.02) 2px, rgba(0, 245, 160, 0.02) 4px)",
      },
      boxShadow: {
        // ── Glows Neon Intensos ───────────────────────────────
        neon: "0 0 20px rgba(0, 245, 160, 0.25), 0 0 50px rgba(0, 245, 160, 0.10), 0 0 80px rgba(0, 245, 160, 0.05)",
        "neon-strong": "0 0 30px rgba(0, 245, 160, 0.35), 0 0 70px rgba(0, 245, 160, 0.15)",
        "neon-subtle": "0 0 10px rgba(0, 245, 160, 0.15), 0 0 25px rgba(0, 245, 160, 0.06)",
        "neon-blue":
          "0 0 20px rgba(0, 224, 255, 0.25), 0 0 50px rgba(0, 224, 255, 0.10), 0 0 80px rgba(0, 224, 255, 0.05)",
        "neon-purple":
          "0 0 20px rgba(192, 132, 252, 0.25), 0 0 50px rgba(192, 132, 252, 0.10), 0 0 80px rgba(192, 132, 252, 0.05)",
        "neon-pink":
          "0 0 20px rgba(255, 107, 157, 0.25), 0 0 50px rgba(255, 107, 157, 0.10)",
        // ── Sombras Profundas ──────────────────────────────────
        card: "0 8px 32px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255,255,255,0.04)",
        "card-deep": "0 16px 56px rgba(0,0,0,0.65), 0 4px 8px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06)",
        glow: "0 0 0 1px rgba(0,245,160,0.20), 0 0 24px rgba(0,245,160,0.16)",
        "glow-sm": "0 0 6px rgba(0,245,160,0.18), 0 0 16px rgba(0,245,160,0.08)",
        inset: "inset 0 2px 6px 0 rgba(0,0,0,0.35)",
        "inset-light": "inset 0 1px 0 0 rgba(255,255,255,0.08)",
        "inset-green": "inset 0 1px 0 0 rgba(0,245,160,0.12)",
      },
      borderRadius: {
        "2.5xl": "1.25rem",
        "3xl": "1.5rem",
      },
      borderWidth: {
        "micro": "0.5px",
      },
      animation: {
        pulse_slow: "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        pulse_fast: "pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.35s ease-out forwards",
        shimmer: "shimmer 2.4s linear infinite",
        "shimmer-slow": "shimmer 4s linear infinite",
        "shimmer-fast": "shimmer 1.6s linear infinite",
        "glow-pulse": "glowPulse 3s ease-in-out infinite",
        "glow-pulse-fast": "glowPulse 1.8s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        "mesh-shift": "meshShift 20s ease-in-out infinite alternate",
        breathe: "breathe 8s ease-in-out infinite",
        drift: "drift 18s ease-in-out infinite alternate",
        "spin-slow": "spin 12s linear infinite",
        glitch: "glitch 4s ease-in-out infinite",
        scan: "scan 8s linear infinite",
        typewriter: "typewriter 1s steps(20) forwards",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% center" },
          "100%": { backgroundPosition: "-200% center" },
        },
        glowPulse: {
          "0%, 100%": { opacity: "0.4" },
          "50%": { opacity: "0.85" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
        meshShift: {
          "0%": { transform: "translate(0, 0) scale(1)" },
          "100%": { transform: "translate(2%, -1%) scale(1.02)" },
        },
        breathe: {
          "0%, 100%": { opacity: "0.35", transform: "scale(1)" },
          "50%": { opacity: "0.7", transform: "scale(1.05)" },
        },
        drift: {
          "0%": { transform: "translate(0, 0) rotate(0deg)" },
          "100%": { transform: "translate(25px, -12px) rotate(2deg)" },
        },
        glitch: {
          "0%, 90%, 100%": { transform: "translate(0)", opacity: "1" },
          "92%": { transform: "translate(-2px, 1px)", opacity: "0.8" },
          "94%": { transform: "translate(2px, -1px)", opacity: "0.9" },
          "96%": { transform: "translate(-1px, 2px)", opacity: "0.7" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        typewriter: {
          "0%": { width: "0%" },
          "100%": { width: "100%" },
        },
      },
    },
  },
  plugins: [],
};
