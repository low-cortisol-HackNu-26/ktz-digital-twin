import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}", "./store/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0A1217",
        panel: "#10222A",
        line: "#1E3B46",
        accent: "#35C4A8",
        warn: "#F3B33D",
        danger: "#F56A6A"
      }
    }
  },
  plugins: []
};

export default config;
