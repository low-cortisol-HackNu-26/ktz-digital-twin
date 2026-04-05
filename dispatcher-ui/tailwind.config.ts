import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        disp: {
          bg: "#121a24",
          panel: "#1a2230",
          accent: "#4fb3e8",
        },
      },
    },
  },
  plugins: [],
};

export default config;
