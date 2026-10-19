"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { ReactNode } from "react";
import { CircleCheck } from "lucide-react";
import { useReducedMotionPref } from "@/hooks/use-reduced-motion-pref";
import type { IconComponent } from "@/lib/labels";
import { Card } from "@/components/ui/card";
import { Sparkline } from "@/components/charts/sparkline";
import { RingGauge } from "@/components/dashboard/ring-gauge";

type Tone = "default" | "critical" | "ok" | "warning";

const TONE_TEXT: Record<Tone, string> = {
  default: "text-muted-foreground",
  critical: "text-sev-critical",
  ok: "text-ok",
  warning: "text-sev-high",
};

function useCountUp(target: number): number {
  const reduced = useReducedMotionPref();
  const [value, setValue] = useState(0);
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    if (reduced || animated) {
      const frame = requestAnimationFrame(() => setValue(target));
      return () => cancelAnimationFrame(frame);
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / 600);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        setAnimated(true);
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, reduced, animated]);

  return value;
}

interface KpiTileProps {
  label: string;
  icon: IconComponent;
  value?: number;
  valueText?: string;
  href?: string;
  tone?: Tone;
  featured?: boolean;
  spark?: number[];
  ring?: { value: number; total: number };
  footer?: ReactNode;
  allClear?: boolean;
}

export function KpiTile({
  label,
  icon: Icon,
  value,
  valueText,
  href,
  tone = "default",
  featured = false,
  spark,
  ring,
  footer,
  allClear = false,
}: KpiTileProps) {
  const counted = useCountUp(value ?? 0);
  const display = valueText ?? String(value ?? counted);

  const body = (
    <Card
      className={`relative h-full overflow-hidden transition-colors ${
        href ? "hover:border-border-strong hover:bg-surface-2/60" : ""
      } ${featured ? "border-border-strong" : ""}`}
    >
      <div className="flex h-full flex-col gap-2 p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <span className={allClear ? "text-ok" : TONE_TEXT[tone]}>
            {allClear ? (
              <CircleCheck className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Icon className="h-4 w-4" aria-hidden="true" />
            )}
          </span>
        </div>
        <div className="flex items-end gap-3">
          {ring ? (
            <RingGauge
              value={ring.value}
              total={ring.total}
              label={`${ring.value} of ${ring.total} cameras online`}
            />
          ) : null}
          <p
            className={`font-mono tabular-nums leading-none tracking-tight ${
              featured ? "text-4xl" : "text-2xl"
            }`}
          >
            {display}
          </p>
        </div>
        {allClear ? (
          <p className="text-xs text-ok">No pending incidents</p>
        ) : null}
        {spark && spark.length > 0 ? <Sparkline values={spark} /> : null}
        {footer}
      </div>
    </Card>
  );

  if (href) {
    return (
      <Link href={href} className="block h-full rounded-lg">
        {body}
      </Link>
    );
  }
  return body;
}
