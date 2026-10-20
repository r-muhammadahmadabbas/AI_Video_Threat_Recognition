import { cn } from "@/lib/utils";

export function StatusDot({
  online,
  label,
  className,
}: {
  online: boolean;
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn("relative flex h-2 w-2 shrink-0", className)}
      role={label ? "img" : undefined}
      aria-label={label}
    >
      {online ? (
        <span
          className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60"
          aria-hidden="true"
        />
      ) : null}
      <span
        className={cn(
          "relative inline-flex h-2 w-2 rounded-full",
          online ? "bg-ok" : "bg-muted-foreground/40",
        )}
        aria-hidden="true"
      />
    </span>
  );
}
