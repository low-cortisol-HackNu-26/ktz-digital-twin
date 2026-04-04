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
          bg: "#0a0e14",
          panel: "#121820",
          border: "#1e2836",
        },
        health: {
          normal: "#22c55e",
          warning: "#eab308",
          critical: "#ef4444",
        },
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
      },
      animation: {
        "critical-pulse": "critical-pulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
