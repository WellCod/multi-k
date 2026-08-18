import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Paleta utilitária: hierarquia por peso e espaço.
      // Cor só onde carrega informação (status, alerta, divergência).
      colors: {
        brand: {
          DEFAULT: "#2563EB", // azul neutro — identidade sem decoração
          dark: "#1D4ED8",
        },
        status: {
          ok: "#16A34A",
          warning: "#D97706",
          error: "#DC2626",
          info: "#2563EB",
        },
      },
      fontFamily: {
        // Inter: tipografia utilitária, densidade alta, fácil de ler em tabelas
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
