import * as React from "react";
import { cn } from "@/lib/utils";

interface SeparatorProps extends React.HTMLAttributes<HTMLHRElement> {
  orientation?: "horizontal" | "vertical";
  className?: string;
  decorative?: boolean;
  orient?: "horizontal" | "vertical";
}

const Separator = React.forwardRef<HTMLHRElement, SeparatorProps>(
  ({ className, orientation = "horizontal", decorative, ...props }, ref) => {
    return (
      <hr
        ref={ref}
        className={cn(
          "shrink-0 border",
          className,
          orientation === "horizontal" ? "h-[1px] w-full" : "w-[1px] h-full",
        )}
        aria-orientation={orientation}
        {...(decorative ? { "aria-hidden": true } : {})}
        {...props}
      />
    );
  },
);
Separator.displayName = "Separator";

export { Separator };
