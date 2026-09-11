import { Children, cloneElement, isValidElement, useId, type HTMLAttributes, type ReactElement, type ReactNode } from "react";
import { cn } from "@/lib/utils";

const gaps = { 0: "gap-0", 1: "gap-1", 2: "gap-2", 3: "gap-3", 4: "gap-4", 6: "gap-6", 8: "gap-8" };
type LayoutProps = HTMLAttributes<HTMLDivElement> & { gap?: keyof typeof gaps };

export function Stack({ gap = 4, className, ...props }: LayoutProps) {
  return <div className={cn("flex flex-col min-w-0", gaps[gap], className)} {...props} />;
}
export function Row({ gap = 3, className, ...props }: LayoutProps) {
  return <div className={cn("flex items-center min-w-0", gaps[gap], className)} {...props} />;
}
export function Page({ children, title, actions }: { children: ReactNode; title?: string; actions?: ReactNode }) {
  return <div className="page"><Stack>{title && <Row className="justify-between flex-wrap"><h1 className="text-xl font-semibold">{title}</h1>{actions}</Row>}{children}</Stack></div>;
}

export function Field({ label, error, hint, children }: { label: string; error?: string; hint?: string; children: ReactNode }) {
  const id = useId();
  const description = `${id}-description`;
  return <Stack gap={1} className="field">
    <label htmlFor={id} className="text-sm font-medium">{label}</label>
    {Children.map(children, child => isValidElement(child) ? cloneElement(child as ReactElement<HTMLAttributes<HTMLElement>>, { id, "aria-describedby": description, "aria-invalid": !!error }) : child)}
    <span id={description} className={cn("field-message text-xs", error ? "text-danger" : "text-muted")} role={error ? "alert" : undefined}>{error || hint || "\u00a0"}</span>
  </Stack>;
}
