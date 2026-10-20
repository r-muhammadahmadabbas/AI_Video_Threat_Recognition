"use client";

import * as THREE from "three";

const cache = new Map<string, THREE.Color>();

export function cssColor(value: string, fallback: string): THREE.Color {
  const key = value || fallback;
  const cached = cache.get(key);
  if (cached) return cached;

  let color: THREE.Color | null = null;
  if (typeof document !== "undefined") {
    try {
      const canvas = document.createElement("canvas");
      canvas.width = 1;
      canvas.height = 1;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (context) {
        context.fillStyle = "#010203";
        context.fillStyle = value || fallback;
        if (
          context.fillStyle === "#010203" &&
          (value || fallback).trim().toLowerCase() !== "#010203"
        ) {
          context.fillStyle = fallback;
        }
        context.fillRect(0, 0, 1, 1);
        const [r, g, b] = context.getImageData(0, 0, 1, 1).data;
        color = new THREE.Color().setRGB(
          r / 255,
          g / 255,
          b / 255,
          THREE.SRGBColorSpace,
        );
      }
    } catch {
      color = null;
    }
  }

  if (!color) color = new THREE.Color(fallback);
  cache.set(key, color);
  return color;
}

export function readCssToken(token: string): string {
  if (typeof window === "undefined") return "";
  return getComputedStyle(document.documentElement)
    .getPropertyValue(token)
    .trim();
}
