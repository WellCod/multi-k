import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: "var(--surface)", canvas: "var(--canvas)", ink: "var(--ink)",
        muted: "var(--muted)", line: "var(--line)", selected: "var(--selected)",
        action: "var(--action)", success: "var(--success)", warning: "var(--warning)",
        danger: "var(--danger)", divergence: "var(--divergence)",
      },
      fontFamily: {
        // Inter: tipografia utilitária, densidade alta, fácil de ler em tabelas
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["Inter", "system-ui", "sans-serif"],
      },
      fontSize: { xs: ["12px", "16px"], sm: ["14px", "20px"], base: ["16px", "24px"], lg: ["20px", "28px"], xl: ["24px", "32px"] },
      borderRadius: { DEFAULT: "4px" },
      boxShadow: { panel: "0 4px 16px rgb(30 41 59 / 0.12)" },
      maxWidth: { workspace: "1440px" },
    },
  },
  plugins: [],
} satisfies Config;
