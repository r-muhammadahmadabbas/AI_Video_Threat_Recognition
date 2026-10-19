"use client";

import { Radio } from "lucide-react";
import { LiveQrCard } from "@/components/live-qr-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const steps = [
  {
    title: "Scan the QR code",
    description:
      "Point your phone camera at the code. The capture page opens in your mobile browser and asks for camera permission.",
  },
  {
    title: "Record live",
    description:
      "Your rear camera streams into the page. Press record and capture the scene in real time.",
  },
  {
    title: "Automatic analysis",
    description:
      "When you stop recording, the clip is uploaded and analyzed. You get the full threat report with annotated frames.",
  },
];

export default function LivePage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <Radio className="h-5 w-5 text-primary" aria-hidden="true" />
          Live capture
        </h1>
        <p className="text-sm text-muted-foreground">
          Record from a phone and analyze the clip instantly
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">
            Connect a device
          </CardTitle>
        </CardHeader>
        <CardContent>
          <LiveQrCard />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {steps.map((step, index) => (
          <Card key={step.title}>
            <CardContent className="flex gap-3 p-5">
              <span
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-xs font-semibold text-primary"
                aria-hidden="true"
              >
                {index + 1}
              </span>
              <div>
                <p className="text-sm font-medium">{step.title}</p>
                <p className="mt-1.5 text-sm text-muted-foreground">
                  {step.description}
                </p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
