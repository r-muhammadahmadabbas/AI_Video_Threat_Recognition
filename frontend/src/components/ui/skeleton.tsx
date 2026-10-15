import * as React from "react";
import { cn } from "@/lib/utils";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("h-[1rem] w-full rounded-md bg-surface-2", className)}
      {...props}
    />
  ),
);
Skeleton.displayName = "Skeleton";

export { Skeleton };
