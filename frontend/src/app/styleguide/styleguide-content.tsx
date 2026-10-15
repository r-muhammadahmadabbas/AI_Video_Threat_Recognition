"use client";

import { TriangleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SeverityBadge, StatusBadge } from "@/components/status-badges";
import { classInfo } from "@/lib/labels";

const TOKENS = [
  ["background", "var(--background)"],
  ["surface-1", "var(--surface-1)"],
  ["surface-2", "var(--surface-2)"],
  ["surface-3", "var(--surface-3)"],
  ["border-strong", "var(--border-strong)"],
  ["muted-foreground", "var(--muted-foreground)"],
  ["foreground", "var(--foreground)"],
  ["primary", "var(--primary)"],
  ["sev-critical", "var(--sev-critical)"],
  ["sev-high", "var(--sev-high)"],
  ["sev-medium", "var(--sev-medium)"],
  ["sev-low", "var(--sev-low)"],
  ["ok", "var(--ok)"],
] as const;

const SEVERITIES = ["critical", "very_high", "high", "medium", "low", "other"];
const STATUSES = [
  "detected",
  "pending_review",
  "verified",
  "dismissed",
  "merged",
  "notification_failed",
];
const CLASSES = [
  "firearm",
  "melee_weapon",
  "explosive",
  "blunt_weapon",
  "fire_smoke",
  "tool",
  "person",
  "fall",
  "violence",
  "crowd",
];

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      {children}
      <Separator />
    </section>
  );
}

export function StyleguideContent() {
  return (
    <main className="mx-auto max-w-5xl space-y-10 p-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">
          Obsidian Ops — Styleguide
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Dev-only reference for tokens, primitives, and threat vocabulary.
        </p>
      </header>

      <Section title="Tokens">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          {TOKENS.map(([name, value]) => (
            <div key={name} className="space-y-2">
              <div
                className="h-14 rounded-md border border-border-strong"
                style={{ background: value }}
              />
              <p className="text-xs text-muted-foreground">{name}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Glass">
        <div
          className="grid gap-4 rounded-lg border border-border p-6 sm:grid-cols-2"
          style={{
            backgroundImage:
              "repeating-linear-gradient(45deg, var(--surface-3) 0 12px, var(--surface-1) 12px 24px)",
          }}
        >
          <div className="glass rounded-lg border border-border-strong p-4">
            <p className="text-sm font-medium">.glass</p>
            <p className="text-xs text-muted-foreground">blur 12px</p>
          </div>
          <div className="glass-hud rounded-lg border border-border-strong p-4">
            <p className="text-sm font-medium">.glass-hud</p>
            <p className="text-xs text-muted-foreground">blur 16px</p>
          </div>
        </div>
      </Section>

      <Section title="Typography">
        <div className="space-y-2">
          <p className="text-2xl font-semibold tracking-tight">Heading 24</p>
          <p className="text-lg font-semibold">Heading 18</p>
          <p className="text-base font-semibold">Heading 16</p>
          <p className="text-sm">Body 14 — default UI size.</p>
          <p className="text-xs text-muted-foreground">
            Caption 12 — secondary.
          </p>
          <p className="font-mono text-sm tabular-nums">0123456789 — metrics</p>
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="link">Link</Button>
          <Button size="sm">Small</Button>
          <Button size="lg">Large</Button>
          <Button size="icon" aria-label="Icon button" variant="outline">
            <TriangleAlert className="h-4 w-4" />
          </Button>
        </div>
      </Section>

      <Section title="Badges & severity">
        <div className="flex flex-wrap gap-3">
          <Badge>Default</Badge>
          <Badge variant="secondary">Secondary</Badge>
          <Badge variant="destructive">Destructive</Badge>
          <Badge variant="success">Success</Badge>
          <Badge variant="warning">Warning</Badge>
          <Badge variant="info">Info</Badge>
        </div>
        <div className="flex flex-wrap gap-3">
          {SEVERITIES.map((s) => (
            <SeverityBadge key={s} severity={s} />
          ))}
        </div>
        <div className="flex flex-wrap gap-3">
          {STATUSES.map((s) => (
            <StatusBadge key={s} status={s} />
          ))}
        </div>
      </Section>

      <Section title="Threat vocabulary">
        <div className="flex flex-wrap gap-3">
          {CLASSES.map((name) => {
            const info = classInfo(name);
            const Icon = info.icon;
            return (
              <span
                key={name}
                className="inline-flex items-center gap-2 rounded-md border border-border-strong bg-surface-2 px-3 py-1.5 text-[13px]"
              >
                <Icon className="h-4 w-4 text-muted-foreground" />
                {info.label}
              </span>
            );
          })}
        </div>
      </Section>

      <Section title="Alerts">
        <div className="space-y-3">
          <Alert>
            <TriangleAlert className="h-4 w-4" />
            <AlertTitle>Neutral info</AlertTitle>
            <AlertDescription>
              Default alert for ambient information.
            </AlertDescription>
          </Alert>
          <Alert variant="warning">
            <TriangleAlert className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>A condition needs attention.</AlertDescription>
          </Alert>
          <Alert variant="destructive">
            <TriangleAlert className="h-4 w-4" />
            <AlertTitle>Critical</AlertTitle>
            <AlertDescription>Action required immediately.</AlertDescription>
          </Alert>
        </div>
      </Section>

      <Section title="Forms">
        <div className="grid max-w-md gap-4">
          <div className="space-y-2">
            <Label htmlFor="sg-name">Camera name</Label>
            <Input id="sg-name" placeholder="Gate 3 — North" />
          </div>
          <div className="space-y-2">
            <Label>Severity floor</Label>
            <Select defaultValue="medium">
              <SelectTrigger aria-label="Severity floor">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="medium">Medium</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="critical">Critical</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </Section>

      <Section title="Tabs & progress">
        <Tabs defaultValue="one">
          <TabsList>
            <TabsTrigger value="one">Overview</TabsTrigger>
            <TabsTrigger value="two">Events</TabsTrigger>
            <TabsTrigger value="three">Config</TabsTrigger>
          </TabsList>
          <TabsContent value="one" className="text-sm">
            Overview panel content.
          </TabsContent>
          <TabsContent value="two" className="text-sm">
            Events panel content.
          </TabsContent>
          <TabsContent value="three" className="text-sm">
            Config panel content.
          </TabsContent>
        </Tabs>
        <div className="max-w-sm space-y-2">
          <Progress value={72} />
          <Progress value={38} className="[&>div]:bg-sev-high" />
        </div>
      </Section>

      <Section title="Dialog & skeleton">
        <div className="flex items-center gap-4">
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline">Open dialog</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Confirm action</DialogTitle>
                <DialogDescription>
                  Dialogs render on a glass surface with a 160ms entrance.
                </DialogDescription>
              </DialogHeader>
              <div className="flex justify-end gap-2">
                <Button variant="ghost">Cancel</Button>
                <Button>Confirm</Button>
              </div>
            </DialogContent>
          </Dialog>
          <div className="w-48 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </div>
      </Section>

      <Section title="Cards">
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Card title</CardTitle>
            <CardDescription>Tier-1 surface, hairline border.</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Cards sit on <code className="font-mono text-xs">surface-1</code>{" "}
            with a <code className="font-mono text-xs">border</code> hairline.
          </CardContent>
        </Card>
      </Section>
    </main>
  );
}
