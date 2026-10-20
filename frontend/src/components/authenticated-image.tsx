"use client";

import { ImageOff, Loader2 } from "lucide-react";
import { useAuthenticatedBlob } from "@/hooks/use-authenticated-blob";
import { cn } from "@/lib/utils";

interface AuthenticatedImageProps {
  src: string;
  alt: string;
  className?: string;
}

export function AuthenticatedImage({
  src,
  alt,
  className,
}: AuthenticatedImageProps) {
  const { objectUrl, loading, error } = useAuthenticatedBlob(src);

  if (loading) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-md border border-border bg-muted/40",
          className,
        )}
      >
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error || !objectUrl) {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border text-muted-foreground",
          className,
        )}
      >
        <ImageOff className="h-5 w-5" />
        <span className="text-xs">Preview unavailable</span>
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={objectUrl} alt={alt} className={className} />
  );
}
