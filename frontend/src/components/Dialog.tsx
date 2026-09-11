import { useEffect, useId, useRef, type ReactNode } from "react";

export function Dialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog?.showModal();
    return () => { dialog?.close(); previous?.focus(); };
  }, []);
  return <dialog ref={ref} aria-labelledby={titleId} onCancel={event => { event.preventDefault(); onClose(); }} className="w-full max-w-2xl rounded border border-line bg-surface text-ink p-4 shadow-panel backdrop:bg-black/40">
    <h2 id={titleId} className="text-lg font-semibold mb-4">{title}</h2>{children}
  </dialog>;
}
