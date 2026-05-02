import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10px] font-mono font-bold uppercase tracking-widest transition-colors",
  {
    variants: {
      variant: {
        default: "border-neutral-200 bg-neutral-50 text-neutral-600",
        green: "border-[#c5e87a] bg-[#f0fad8] text-[#5e9100]",
        red: "border-red-200 bg-red-50 text-red-600",
        amber: "border-amber-200 bg-amber-50 text-amber-700",
        outline: "border-neutral-300 bg-transparent text-neutral-600",
        ghost: "border-transparent bg-transparent text-neutral-500",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
