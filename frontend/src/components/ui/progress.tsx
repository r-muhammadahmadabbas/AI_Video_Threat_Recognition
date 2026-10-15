import * as React from "react";
import { cn } from "@/lib/utils";

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value = 0, ...props }, ref) => (
    <div
      ref={ref}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn(
        "relative h-1.5 w-full overflow-hidden rounded-full bg-surface-3",
        className,
      )}
      {...props}
    >
      <div
        className="h-full rounded-full bg-primary transition-transform duration-300 ease-out-expo"
        style={{ transform: `translateX(-${100 - value}%)` }}
      />
    </div>
  ),
);
Progress.displayName = "Progress";

export { Progress };
