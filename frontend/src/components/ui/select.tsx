import * as React from "react";
import { cn } from "@/lib/utils";

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  error?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, error, children, ...props }, ref) => (
    <div className="w-full">
      <select
        ref={ref}
        className={cn(
          "flex h-9 w-full rounded border border-line bg-surface text-ink px-3 py-1 text-sm shadow-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action disabled:cursor-not-allowed disabled:opacity-50",
          error && "border-line",
          className,
        )}
        {...props}
      >
        {children}
      </select>
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  ),
);
Select.displayName = "Select";
