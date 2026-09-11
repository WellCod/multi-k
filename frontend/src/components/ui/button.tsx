import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "control-primary hover:opacity-90",
        outline:
          "border border-line bg-surface text-ink hover:bg-canvas ",
        ghost: "hover:bg-canvas text-ink ",
        destructive: "border border-danger text-danger bg-surface hover:bg-canvas",
        secondary: "bg-canvas text-ink hover:bg-surface ",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-9 px-3 text-sm",
        lg: "h-9 px-6",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
