import { useRef, useState } from "react";
import { createPortal } from "react-dom";

interface TooltipProps {
  text: string;
  children: React.ReactNode;
  position?: "top" | "bottom";
}

interface Coords {
  x: number;
  y: number;
}

const GAP = 8; // px entre o elemento e o balão
const MAX_W = 280; // largura máxima do tooltip em px

export function Tooltip({ text, children, position = "top" }: TooltipProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const [coords, setCoords] = useState<Coords | null>(null);

  const show = () => {
    if (!ref.current) return;
    const r = ref.current.getBoundingClientRect();
    // Centraliza horizontalmente no trigger, clampa para não sair da viewport
    const rawX = r.left + r.width / 2;
    const x = Math.max(MAX_W / 2 + 4, Math.min(rawX, window.innerWidth - MAX_W / 2 - 4));
    const y = position === "top" ? r.top : r.bottom;
    setCoords({ x, y });
  };

  const hide = () => setCoords(null);

  return (
    <span
      ref={ref}
      className="inline-flex"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}

      {coords &&
        createPortal(
          <span
            className="pointer-events-none fixed z-50"
            style={{
              left: coords.x,
              top: coords.y,
              transform:
                position === "top"
                  ? `translate(-50%, calc(-100% - ${GAP}px))`
                  : `translate(-50%, ${GAP}px)`,
              maxWidth: MAX_W,
            }}
          >
            {/* seta — fica embaixo do balão quando position=top */}
            {position === "top" && (
              <span className="block w-2 h-2 bg-surface border-b border-r border-line rotate-45 mx-auto translate-y-0" />
            )}

            <span className="block bg-surface border border-line rounded shadow-panel px-3 py-2 text-xs text-ink text-center leading-relaxed">
              {text}
            </span>

            {position === "bottom" && (
              <span className="block w-2 h-2 bg-surface border-t border-l border-line rotate-45 mx-auto translate-y-0" />
            )}
          </span>,
          document.body,
        )}
    </span>
  );
}
