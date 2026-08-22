import { createContext, useContext, useState } from "react";

interface DarkModeCtx {
  dark: boolean;
  toggle: () => void;
}

export const DarkModeContext = createContext<DarkModeCtx>({
  dark: false,
  toggle: () => {},
});

function applyTheme(dark: boolean) {
  if (dark) {
    document.documentElement.classList.add("dark");
    localStorage.setItem("theme", "dark");
  } else {
    document.documentElement.classList.remove("dark");
    localStorage.setItem("theme", "light");
  }
}

export function useDarkModeState(): DarkModeCtx {
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains("dark"),
  );

  const toggle = () => {
    const next = !dark;
    applyTheme(next);
    setDark(next);
  };

  return { dark, toggle };
}

export function useDarkMode() {
  return useContext(DarkModeContext);
}
