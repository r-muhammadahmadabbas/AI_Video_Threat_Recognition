"use client";

import type { ReactNode } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/empty-state";

interface ChartCardProps {
  title: string;
  description?: string;
  action?: ReactNode;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  minHeight?: string;
  children: ReactNode;
}

export function ChartCard({
  title,
  description,
  action,
  loading = false,
  error = null,
  onRetry,
  minHeight = "h-64",
  children,
}: ChartCardProps) {
  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-2 pb-3">
        <div>
          <CardTitle className="text-base">{title}</CardTitle>
          {description ? (
            <CardDescription className="mt-1">{description}</CardDescription>
          ) : null}
        </div>
        {action}
      </CardHeader>
      <CardContent>
        {error ? (
          <div className="flex flex-col items-start gap-2">
            <ErrorState message={error} />
            {onRetry ? (
              <Button variant="outline" size="sm" onClick={onRetry}>
                Retry
              </Button>
            ) : null}
          </div>
        ) : loading ? (
          <Skeleton className={minHeight} />
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}
