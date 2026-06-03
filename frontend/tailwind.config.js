/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
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
          DEFAULT: "#0a0f1a",
          card: "rgba(15, 23, 42, 0.6)",
          elevated: "rgba(30, 41, 59, 0.5)",
          border: "rgba(255, 255, 255, 0.07)",
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "mesh-gradient":
          "linear-gradient(135deg, #0a0f1a 0%, #1a1033 50%, #0d2137 100%)",
        "gradient-hero":
          "linear-gradient(135deg, rgba(0,255,136,0.04) 0%, rgba(0,212,255,0.04) 50%, rgba(168,85,247,0.04) 100%)",
      },
      boxShadow: {
        neon: "0 0 20px rgba(0, 255, 136, 0.15)",
        "neon-blue": "0 0 20px rgba(0, 212, 255, 0.15)",
        "neon-purple": "0 0 20px rgba(168, 85, 247, 0.15)",
        "card": "0 4px 24px rgba(0,0,0,0.4)",
      },
      animation: {
        pulse_slow: "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.3s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
