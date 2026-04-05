import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        cabin: {
          bg: "white",
          panel: "white",
          border: "gray",
        },
        health: {
          normal: "#22c55e",
          warning: "#eab308",
          critical: "#ef4444",
        },
        primary: "#374151",
        secondary: "#717182",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      keyframes: {
        "critical-pulse": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(239, 68, 68, 0.45)" },
          "50%": { boxShadow: "0 0 24px 4px rgba(239, 68, 68, 0.35)" },
        },
        "health-halo-normal": {
          "0%, 100%": {
            boxShadow:
              "0 0 0 2px rgba(34, 197, 94, 0.28), 0 0 28px rgba(34, 197, 94, 0.18)",
          },
          "50%": {
            boxShadow:
              "0 0 0 3px rgba(34, 197, 94, 0.5), 0 0 48px rgba(34, 197, 94, 0.32)",
          },
        },
        "health-halo-warning": {
          "0%, 100%": {
            boxShadow:
              "0 0 0 2px rgba(234, 179, 8, 0.4), 0 0 32px rgba(234, 179, 8, 0.22)",
          },
          "50%": {
            boxShadow:
              "0 0 0 4px rgba(234, 179, 8, 0.65), 0 0 52px rgba(234, 179, 8, 0.38)",
          },
        },
        "health-halo-critical": {
          "0%, 100%": {
            boxShadow:
              "0 0 0 2px rgba(239, 68, 68, 0.55), 0 0 36px rgba(239, 68, 68, 0.35)",
          },
          "50%": {
            boxShadow:
              "0 0 0 5px rgba(239, 68, 68, 0.85), 0 0 64px rgba(239, 68, 68, 0.55)",
          },
        },
        "panel-glow-warning": {
          "0%, 100%": {
            boxShadow:
              "0 0 0 2px rgba(245, 158, 11, 0.5), 0 4px 22px rgba(245, 158, 11, 0.28)",
          },
          "50%": {
            boxShadow:
              "0 0 0 3px rgba(245, 158, 11, 0.8), 0 10px 36px rgba(245, 158, 11, 0.48)",
          },
        },
        "panel-glow-critical": {
          "0%, 100%": {
            boxShadow:
              "0 0 0 2px rgba(239, 68, 68, 0.6), 0 6px 26px rgba(239, 68, 68, 0.35)",
          },
          "50%": {
            boxShadow:
              "0 0 0 4px rgba(239, 68, 68, 0.95), 0 12px 44px rgba(239, 68, 68, 0.55)",
          },
        },
        "trend-toast-in": {
          from: { opacity: "0", transform: "translateY(-0.5rem)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "critical-pulse": "critical-pulse 2s ease-in-out infinite",
        "health-halo-normal": "health-halo-normal 2.8s ease-in-out infinite",
        "health-halo-warning": "health-halo-warning 2.2s ease-in-out infinite",
        "health-halo-critical": "health-halo-critical 1.5s ease-in-out infinite",
        "panel-glow-warning": "panel-glow-warning 2s ease-in-out infinite",
        "panel-glow-critical": "panel-glow-critical 1.35s ease-in-out infinite",
        "trend-toast-in": "trend-toast-in 0.35s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
