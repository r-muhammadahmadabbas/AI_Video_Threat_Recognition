"use client";

import { useMemo } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { PieChart as PieChartIcon } from "lucide-react";
import type { Incident } from "@/types";
import { useReducedMotionPref } from "@/hooks/use-reduced-motion-pref";
import { severityInfo, type IconComponent } from "@/lib/labels";
import { EmptyState } from "@/components/empty-state";
import { ChartCard } from "@/components/charts/chart-card";
import { ChartDataTable } from "@/components/charts/chart-data-table";
import { useChartColors } from "@/components/charts/use-chart-colors";
import {
  SEVERITY_KEYS,
  severityCounts,
  type SeverityKey,
} from "@/components/charts/use-incident-series";

interface SeverityDonutProps {
  incidents: Incident[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export function SeverityDonut({
  incidents,
  loading = false,
  error = null,
  onRetry,
}: SeverityDonutProps) {
  const colors = useChartColors();
  const reduced = useReducedMotionPref();
  const counts = useMemo(() => severityCounts(incidents), [incidents]);
  const total = incidents.length;

  const colorFor: Record<SeverityKey, string> = {
    critical: colors.critical,
    high: colors.high,
    medium: colors.medium,
    low: colors.low,
  };

  const data = SEVERITY_KEYS.map((key) => {
    const info = severityInfo(key);
    const value = counts[key];
    return {
      key,
      name: info.label,
      value,
      color: colorFor[key],
      icon: info.icon as IconComponent,
      percent: total > 0 ? Math.round((value / total) * 100) : 0,
    };
  });

  return (
    <ChartCard
      title="Severity distribution"
      description="Share of latest incidents by severity"
      loading={loading}
      error={error}
      onRetry={onRetry}
      minHeight="h-56"
    >
      {total === 0 ? (
        <EmptyState
          title="Nothing to chart"
          description="No incidents in the current data set."
          icon={PieChartIcon}
        />
      ) : (
        <>
          <div className="flex flex-col items-center gap-4 sm:flex-row">
            <div className="h-40 w-40 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart accessibilityLayer>
                  <Pie
                    data={data}
                    dataKey="value"
                    nameKey="name"
                    innerRadius="62%"
                    outerRadius="88%"
                    paddingAngle={2}
                    stroke="none"
                    isAnimationActive={!reduced}
                    animationDuration={600}
                  >
                    {data.map((entry) => (
                      <Cell key={entry.key} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: colors.surface2,
                      borderColor: colors.border,
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    itemStyle={{ color: colors.foreground }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="flex w-full flex-col gap-2 text-sm">
              {data.map((entry) => {
                const Icon = entry.icon;
                return (
                  <li key={entry.key} className="flex items-center gap-2">
                    <Icon
                      className="h-4 w-4 shrink-0"
                      style={{ color: entry.color }}
                      aria-hidden="true"
                    />
                    <span className="flex-1 truncate">{entry.name}</span>
                    <span className="font-mono text-sm tabular-nums">
                      {entry.value}
                    </span>
                    <span className="w-9 text-right font-mono text-xs text-muted-foreground">
                      {entry.percent}%
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
          <ChartDataTable
            columns={["Severity", "Count", "Share"]}
            rows={data.map((entry) => [
              entry.name,
              entry.value,
              `${entry.percent}%`,
            ])}
          />
        </>
      )}
    </ChartCard>
  );
}
