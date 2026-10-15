"use client";

import { Radio } from "lucide-react";
import { LiveQrCard } from "@/components/live-qr-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const steps = [
  {
    title: "1. Scan the QR code",
    description:
      "Point your phone camera at the code. The capture page opens in your mobile browser and asks for camera permission.",
  },
  {
    title: "2. Record live",
    description:
      "Your rear camera streams into the page. Press record and capture the scene in real time.",
  },
  {
    title: "3. Automatic analysis",
    description:
      "When you stop recording, the clip is uploaded and analyzed. You get the full threat report with annotated frames.",
  },
];

export default function LivePage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Radio className="h-6 w-6 text-primary" />
          Live Stream
        </h1>
        <p className="text-sm text-muted-foreground">
          Stream live content from any mobile device and analyze it instantly
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Mobile live capture</CardTitle>
        </CardHeader>
        <CardContent>
          <LiveQrCard />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {steps.map((step) => (
          <Card key={step.title}>
            <CardContent className="p-5">
              <p className="font-medium">{step.title}</p>
              <p className="mt-2 text-sm text-muted-foreground">
                {step.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
