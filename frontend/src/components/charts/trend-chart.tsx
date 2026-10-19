"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle } from "lucide-react";
import type { Incident } from "@/types";
import { useReducedMotionPref } from "@/hooks/use-reduced-motion-pref";
import { severityInfo } from "@/lib/labels";
import { EmptyState } from "@/components/empty-state";
import { ChartCard } from "@/components/charts/chart-card";
import { ChartDataTable } from "@/components/charts/chart-data-table";
import { useChartColors } from "@/components/charts/use-chart-colors";
import {
  buildTrend,
  SEVERITY_KEYS,
  type SeverityKey,
  type TrendMode,
} from "@/components/charts/use-incident-series";

interface TrendChartProps {
  incidents: Incident[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  caption?: string;
}

export function TrendChart({
  incidents,
  loading = false,
  error = null,
  onRetry,
  caption,
}: TrendChartProps) {
  const colors = useChartColors();
  const reduced = useReducedMotionPref();
  const [mode, setMode] = useState<TrendMode>("24h");
  const data = useMemo(() => buildTrend(incidents, mode), [incidents, mode]);

  const colorFor: Record<SeverityKey, string> = {
    critical: colors.critical,
    high: colors.high,
    medium: colors.medium,
    low: colors.low,
  };

  return (
    <ChartCard
      title="Incident trend"
      description={caption}
      loading={loading}
      error={error}
      onRetry={onRetry}
      action={
        <div
          className="flex items-center gap-1 rounded-md border border-border bg-surface-2 p-0.5"
          role="group"
          aria-label="Trend window"
        >
          {(["24h", "7d"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setMode(option)}
              aria-pressed={mode === option}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                mode === option
                  ? "bg-surface-3 text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {option === "24h" ? "24 hours" : "7 days"}
            </button>
          ))}
        </div>
      }
    >
      {incidents.length === 0 ? (
        <EmptyState
          title="No incidents yet"
          description="Threat events will appear here as they are detected."
          icon={AlertTriangle}
        />
      ) : (
        <>
          <div className="mb-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
            {SEVERITY_KEYS.map((key) => {
              const info = severityInfo(key);
              return (
                <span key={key} className="inline-flex items-center gap-1.5">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: colorFor[key] }}
                    aria-hidden="true"
                  />
                  {info.label}
                </span>
              );
            })}
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={data}
                accessibilityLayer
                margin={{ top: 8, right: 8, bottom: 0, left: -20 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={colors.border}
                  vertical={false}
                />
                <XAxis
                  dataKey="label"
                  tick={{ fill: colors.muted, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  interval={mode === "24h" ? 3 : 0}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fill: colors.muted, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: colors.surface2,
                    borderColor: colors.border,
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  labelStyle={{ color: colors.foreground }}
                  itemStyle={{ color: colors.foreground }}
                />
                {SEVERITY_KEYS.map((key) => (
                  <Area
                    key={key}
                    type="monotone"
                    dataKey={key}
                    name={severityInfo(key).label}
                    stackId="severity"
                    stroke={colorFor[key]}
                    strokeWidth={1.5}
                    fill={colorFor[key]}
                    fillOpacity={0.28}
                    isAnimationActive={!reduced}
                    animationDuration={600}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <ChartDataTable
            columns={[
              "Time",
              ...SEVERITY_KEYS.map((k) => severityInfo(k).label),
            ]}
            rows={data.map((row) => [
              row.label,
              row.critical,
              row.high,
              row.medium,
              row.low,
            ])}
          />
        </>
      )}
    </ChartCard>
  );
}
