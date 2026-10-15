"use client";

import { useState, useSyncExternalStore } from "react";
import { QRCodeSVG } from "qrcode.react";
import {
  Check,
  Copy,
  ExternalLink,
  ShieldAlert,
  Smartphone,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const emptySubscribe = () => () => {};
const getCaptureUrl = () => `${window.location.origin}/live/capture`;
const getServerCaptureUrl = () => "";

export function LiveQrCard() {
  const url = useSyncExternalStore(
    emptySubscribe,
    getCaptureUrl,
    getServerCaptureUrl,
  );
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start sm:gap-6">
      <div className="rounded-xl border border-border bg-white p-4">
        {url ? (
          <QRCodeSVG value={url} size={180} level="M" />
        ) : (
          <div className="h-[180px] w-[180px] animate-pulse rounded bg-muted" />
        )}
      </div>
      <div className="flex flex-1 flex-col gap-3 text-center sm:text-left">
        <div className="flex items-center justify-center gap-2 font-semibold sm:justify-start">
          <Smartphone className="h-5 w-5 text-primary" />
          Scan to stream from your phone
        </div>
        <p className="text-sm text-muted-foreground">
          Open the camera app on your phone, scan this QR code, and the live
          capture page opens with your camera ready. Record footage and it will
          be analyzed immediately when you stop.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
          <Button variant="outline" size="sm" onClick={copy}>
            {copied ? (
              <Check className="h-4 w-4 text-green-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
            {copied ? "Copied" : "Copy link"}
          </Button>
          <Button asChild variant="outline" size="sm">
            <a href={url || "/live/capture"} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" />
              Open capture page
            </a>
          </Button>
        </div>
        <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Mobile browsers require HTTPS (or localhost) to access the camera. Use
          an HTTPS URL or a tunnel when scanning from a phone on the network.
        </div>
      </div>
    </div>
  );
}
