"use client";

import { useState, useCallback } from "react";
import { RuleTrigger } from "@/types";

export function useDetection() {
  const [detections, setDetections] = useState<RuleTrigger[]>([]);

  const processTrigger = useCallback((trigger: RuleTrigger) => {
    setDetections((prev) => [...prev, trigger]);
  }, []);

  return { detections, processTrigger };
}
