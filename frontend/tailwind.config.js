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
        },
        surface: {
          DEFAULT: "#0a0f1a",
          card: "rgba(15, 23, 42, 0.6)",
          elevated: "rgba(30, 41, 59, 0.5)",
        },
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "mesh-gradient":
          "linear-gradient(135deg, #0a0f1a 0%, #1a1033 50%, #0d2137 100%)",
      },
      boxShadow: {
        neon: "0 0 20px rgba(0, 255, 136, 0.15)",
        "neon-blue": "0 0 20px rgba(0, 212, 255, 0.15)",
      },
      animation: {
        pulse_slow: "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
    },
  },
  plugins: [],
};
