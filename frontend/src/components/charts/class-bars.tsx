"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3 } from "lucide-react";
import type { Incident } from "@/types";
import { useReducedMotionPref } from "@/hooks/use-reduced-motion-pref";
import { ruleLabel } from "@/lib/labels";
import { EmptyState } from "@/components/empty-state";
import { ChartCard } from "@/components/charts/chart-card";
import { ChartDataTable } from "@/components/charts/chart-data-table";
import { useChartColors } from "@/components/charts/use-chart-colors";

interface ClassBarsProps {
  incidents: Incident[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export function ClassBars({
  incidents,
  loading = false,
  error = null,
  onRetry,
}: ClassBarsProps) {
  const colors = useChartColors();
  const reduced = useReducedMotionPref();

  const data = useMemo(() => {
    const counts = new Map<string, number>();
    for (const incident of incidents) {
      counts.set(
        incident.event_type,
        (counts.get(incident.event_type) ?? 0) + 1,
      );
    }
    return [...counts.entries()]
      .map(([event, count]) => ({ event, label: ruleLabel(event), count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 8);
  }, [incidents]);

  const height = Math.max(180, data.length * 30 + 24);

  return (
    <ChartCard
      title="Threat class breakdown"
      description="Most frequent classes in the latest incidents"
      loading={loading}
      error={error}
      onRetry={onRetry}
      minHeight="h-56"
    >
      {data.length === 0 ? (
        <EmptyState
          title="Nothing to chart"
          description="No incidents in the current data set."
          icon={BarChart3}
        />
      ) : (
        <>
          <div style={{ height }} className="w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data}
                layout="vertical"
                accessibilityLayer
                margin={{ top: 4, right: 28, bottom: 4, left: 0 }}
              >
                <XAxis type="number" hide allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={150}
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
                  itemStyle={{ color: colors.foreground }}
                  cursor={{ fill: colors.border }}
                />
                <Bar
                  dataKey="count"
                  name="Incidents"
                  fill={colors.primary}
                  radius={[0, 4, 4, 0]}
                  barSize={14}
                  isAnimationActive={!reduced}
                  animationDuration={600}
                >
                  <LabelList
                    dataKey="count"
                    position="right"
                    fill={colors.muted}
                    fontSize={11}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <ChartDataTable
            columns={["Threat class", "Count"]}
            rows={data.map((entry) => [entry.label, entry.count])}
          />
        </>
      )}
    </ChartCard>
  );
}
