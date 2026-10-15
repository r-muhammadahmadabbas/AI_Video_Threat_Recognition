"use client";

import { useEffect, useState } from "react";
import { API_BASE, http } from "@/lib/api";

function toRelative(url: string): string {
  return url.startsWith(API_BASE) ? url.slice(API_BASE.length) : url;
}

export function useAuthenticatedBlob(url: string | null | undefined) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!url);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!url) return;

    let cancelled = false;
    let created: string | null = null;

    Promise.resolve()
      .then(() => {
        setLoading(true);
        setError(false);
        return http.get(toRelative(url), { responseType: "blob" });
      })
      .then((response) => {
        if (cancelled) return;
        created = URL.createObjectURL(response.data);
        setObjectUrl(created);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [url]);

  return {
    objectUrl: url ? objectUrl : null,
    loading: url ? loading : false,
    error: url ? error : false,
  };
}
