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
import { API_BASE } from "@/lib/api";
import type { LiveSession } from "@/types";

const emptySubscribe = () => () => {};
const getPublicBase = () =>
  (process.env.NEXT_PUBLIC_PUBLIC_URL || window.location.origin).replace(
    /\/$/,
    "",
  );
const getServerPublicBase = () => "";

export function LiveQrCard({ session }: { session: LiveSession }) {
  const publicBase = useSyncExternalStore(
    emptySubscribe,
    getPublicBase,
    getServerPublicBase,
  );
  const [copied, setCopied] = useState(false);

  const params = new URLSearchParams({
    session: session.id,
    token: session.capture_token,
    api: API_BASE,
  });
  const url = publicBase
    ? `${publicBase}/live/capture?${params.toString()}`
    : "";
  const apiOnLocalhost = /localhost|127\.0\.0\.1/.test(API_BASE);

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
      <div className="rounded-lg border border-border-strong bg-white p-4">
        {url ? (
          <QRCodeSVG value={url} size={180} level="M" />
        ) : (
          <div className="h-[180px] w-[180px] animate-pulse rounded bg-surface-2" />
        )}
      </div>
      <div className="flex flex-1 flex-col gap-3 text-center sm:text-left">
        <div className="flex items-center justify-center gap-2 font-semibold sm:justify-start">
          <Smartphone className="h-5 w-5 text-primary" />
          Scan to stream from your phone
        </div>
        <p className="text-sm text-muted-foreground">
          Open the camera app on your phone, scan this QR code, and tap Start
          live stream. Frames appear on this dashboard as they arrive, and rule
          detections create incidents automatically.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
          <Button variant="outline" size="sm" onClick={copy} disabled={!url}>
            {copied ? (
              <Check className="h-4 w-4 text-ok" aria-hidden="true" />
            ) : (
              <Copy className="h-4 w-4" aria-hidden="true" />
            )}
            {copied ? "Copied" : "Copy link"}
          </Button>
          <Button asChild variant="outline" size="sm" disabled={!url}>
            <a href={url || "/live/capture"} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
              Open capture page
            </a>
          </Button>
        </div>
        <div className="flex items-start gap-2 rounded-lg border border-sev-high/40 bg-sev-high-bg px-3 py-2 text-xs text-sev-high">
          <ShieldAlert
            className="mt-0.5 h-3.5 w-3.5 shrink-0"
            aria-hidden="true"
          />
          Phone camera access requires HTTPS. Use the public HTTPS frontend URL
          when scanning from a phone on the network.
          {apiOnLocalhost &&
            " The API URL is localhost; set NEXT_PUBLIC_API_URL to the public HTTPS API tunnel before scanning."}
        </div>
      </div>
    </div>
  );
}
