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
        neon: {
          green: "#00ff88",
          blue: "#00d4ff",
          purple: "#a855f7",
          pink: "#ec4899",
          orange: "#ff7730",
          yellow: "#fbbf24",
        },
        surface: {
          DEFAULT: "#070b14",
          50: "#0d111f",
          100: "#111628",
          200: "#161d2f",
          300: "#1c2438",
          card: "rgba(12, 18, 32, 0.72)",
          elevated: "rgba(22, 32, 52, 0.65)",
          border: "rgba(255, 255, 255, 0.08)",
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "mesh-gradient":
          "linear-gradient(145deg, #070b14 0%, #0e0c22 42%, #0a172e 100%)",
        "gradient-hero":
          "linear-gradient(135deg, rgba(0,255,136,0.06) 0%, rgba(0,212,255,0.05) 50%, rgba(168,85,247,0.06) 100%)",
        "brand-gradient":
          "linear-gradient(120deg, #00ff88 0%, #00d4ff 45%, #a855f7 100%)",
        "brand-gradient-subtle":
          "linear-gradient(120deg, rgba(0,255,136,0.15) 0%, rgba(0,212,255,0.12) 45%, rgba(168,85,247,0.15) 100%)",
        "aurora-gradient":
          "linear-gradient(180deg, rgba(0,255,136,0.03) 0%, rgba(0,212,255,0.02) 50%, rgba(168,85,247,0.03) 100%)",
      },
      boxShadow: {
        neon: "0 0 24px rgba(0, 255, 136, 0.18), 0 0 48px rgba(0, 255, 136, 0.06)",
        "neon-subtle": "0 0 12px rgba(0, 255, 136, 0.10), 0 0 24px rgba(0, 255, 136, 0.04)",
        "neon-blue":
          "0 0 24px rgba(0, 212, 255, 0.18), 0 0 48px rgba(0, 212, 255, 0.06)",
        "neon-purple":
          "0 0 24px rgba(168, 85, 247, 0.2), 0 0 48px rgba(168, 85, 247, 0.08)",
        card: "0 8px 32px rgba(0, 0, 0, 0.45), inset 0 1px 0 rgba(255,255,255,0.04)",
        "card-deep": "0 16px 48px rgba(0,0,0,0.55), 0 2px 4px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05)",
        glow: "0 0 0 1px rgba(0,255,136,0.15), 0 0 20px rgba(0,255,136,0.12)",
        "glow-sm": "0 0 8px rgba(0,255,136,0.12), 0 0 16px rgba(0,255,136,0.06)",
        inset: "inset 0 2px 4px 0 rgba(0,0,0,0.25)",
        "inset-light": "inset 0 1px 0 0 rgba(255,255,255,0.06)",
      },
      borderRadius: {
        "2.5xl": "1.25rem",
        "3xl": "1.5rem",
      },
      animation: {
        pulse_slow: "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.35s ease-out forwards",
        shimmer: "shimmer 2.4s linear infinite",
        "shimmer-slow": "shimmer 4s linear infinite",
        "glow-pulse": "glowPulse 3s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        "mesh-shift": "meshShift 20s ease-in-out infinite alternate",
        breathe: "breathe 8s ease-in-out infinite",
        drift: "drift 18s ease-in-out infinite alternate",
        "spin-slow": "spin 12s linear infinite",
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
          "0%, 100%": { opacity: "0.45" },
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
          "0%, 100%": { opacity: "0.4", transform: "scale(1)" },
          "50%": { opacity: "0.7", transform: "scale(1.04)" },
        },
        drift: {
          "0%": { transform: "translate(0, 0) rotate(0deg)" },
          "100%": { transform: "translate(20px, -10px) rotate(2deg)" },
        },
      },
    },
  },
  plugins: [],
};
