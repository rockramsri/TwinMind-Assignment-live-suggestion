import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        panel: "#101826",
        panelBorder: "#23324a",
        panelSoft: "#1a2639",
        accent: "#3abff8",
        accentStrong: "#22d3ee"
      }
    }
  },
  plugins: []
};

export default config;
