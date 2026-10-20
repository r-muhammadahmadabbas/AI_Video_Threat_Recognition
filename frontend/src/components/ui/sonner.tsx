"use client";

import { Toaster as Sonner } from "sonner";

export function Toaster() {
  return (
    <Sonner
      theme="dark"
      position="top-right"
      closeButton
      toastOptions={{
        classNames: {
          toast: "glass border-border-strong text-foreground",
          description: "text-muted-foreground",
          actionButton: "bg-primary text-primary-foreground",
          cancelButton: "bg-surface-3 text-muted-foreground",
          closeButton: "bg-surface-3 border-border-strong",
        },
      }}
    />
  );
}
