"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Canvas,
  useFrame,
  useThree,
  type ThreeEvent,
} from "@react-three/fiber";
import { Html, OrbitControls, PerformanceMonitor } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import * as THREE from "three";
import type { Camera } from "@/types";
import { useReducedMotionPref } from "@/hooks/use-reduced-motion-pref";
import type { CameraLayout, CameraPlacement } from "./use-camera-layout";
import type { SitePing } from "./use-site-pings";
import { cssColor, readCssToken } from "./three-colors";

interface SiteTwin3DProps {
  cameras: Camera[];
  layout: CameraLayout;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  alertLevels: Record<number, string>;
  pings: SitePing[];
  listId: string;
  onFallback: (reason: "performance" | "context") => void;
}

interface Palette {
  ground: THREE.Color;
  grid: THREE.Color;
  primary: THREE.Color;
  offline: THREE.Color;
  muted: THREE.Color;
  critical: THREE.Color;
  high: THREE.Color;
  medium: THREE.Color;
  low: THREE.Color;
}

function usePalette(): Palette {
  return useMemo(() => {
    const token = (name: string, fallback: string) =>
      cssColor(readCssToken(name), fallback);
    return {
      ground: token("--background", "#1c1e24"),
      grid: token("--border-strong", "#33363d"),
      primary: token("--primary", "#66c7e8"),
      offline: token("--surface-3", "#3a3d45"),
      muted: token("--muted-foreground", "#a3a8b4"),
      critical: token("--sev-critical", "#e5484d"),
      high: token("--sev-high", "#f0a23c"),
      medium: token("--sev-medium", "#e8d24a"),
      low: token("--sev-low", "#7aa7e8"),
    };
  }, []);
}

function severityColor(severity: string, palette: Palette): THREE.Color {
  if (severity === "critical" || severity === "very_high") {
    return palette.critical;
  }
  if (severity === "high") return palette.high;
  if (severity === "medium") return palette.medium;
  return palette.low;
}

function CameraNode({
  camera,
  placement,
  selected,
  alert,
  palette,
  onSelect,
}: {
  camera: Camera;
  placement: CameraPlacement;
  selected: boolean;
  alert?: string;
  palette: Palette;
  onSelect: (id: number) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const online = camera.status === "online";
  const color = alert
    ? severityColor(alert, palette)
    : online
      ? palette.primary
      : palette.offline;

  const handleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    onSelect(camera.id);
  };

  return (
    <group
      position={[placement.x, 0, placement.z]}
      rotation={[0, placement.yaw, 0]}
      onClick={handleClick}
      onPointerOver={(event) => {
        event.stopPropagation();
        setHovered(true);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        setHovered(false);
        document.body.style.cursor = "";
      }}
    >
      <mesh position={[0, 0.45, 0]}>
        <boxGeometry args={[0.55, 0.5, 0.55]} />
        <meshStandardMaterial color={color} roughness={0.55} metalness={0.1} />
      </mesh>
      <mesh position={[0, 0.45, 2.1]} rotation={[-Math.PI / 2, 0, 0]}>
        <coneGeometry args={[2, 4.2, 20, 1, true]} />
        <meshBasicMaterial
          color={color}
          transparent
          opacity={online ? 0.16 : 0.07}
          depthWrite={false}
          side={THREE.DoubleSide}
        />
      </mesh>
      {!online ? (
        <mesh position={[0, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.8, 0.9, 28]} />
          <meshBasicMaterial
            color={palette.muted}
            transparent
            opacity={0.5}
            depthWrite={false}
          />
        </mesh>
      ) : (
        <mesh position={[0, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.55, 0.68, 24]} />
          <meshBasicMaterial color={color} depthWrite={false} />
        </mesh>
      )}
      {alert ? (
        <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[1.05, 1.22, 32]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={0.85}
            depthWrite={false}
          />
        </mesh>
      ) : null}
      {selected || hovered ? (
        <Html
          position={[0, 1.7, 0]}
          center
          distanceFactor={16}
          zIndexRange={[30, 0]}
        >
          <div className="pointer-events-none whitespace-nowrap rounded border border-border-strong bg-surface-1 px-1.5 py-0.5 text-[11px] text-foreground shadow-sm">
            {camera.name}
          </div>
        </Html>
      ) : null}
    </group>
  );
}

function PingRing({
  placement,
  color,
}: {
  placement: CameraPlacement;
  color: THREE.Color;
}) {
  const mesh = useRef<THREE.Mesh>(null);
  const invalidate = useThree((state) => state.invalidate);
  const reduced = useReducedMotionPref();
  const start = useRef<number | null>(null);

  useFrame(({ clock }) => {
    if (reduced || !mesh.current) return;
    if (start.current === null) start.current = clock.elapsedTime;
    const progress = Math.min(1, (clock.elapsedTime - start.current) / 3);
    mesh.current.scale.setScalar(0.6 + progress * 3.2);
    const material = mesh.current.material as THREE.MeshBasicMaterial;
    material.opacity = 0.8 * (1 - progress);
    if (progress < 1) invalidate();
  });

  return (
    <mesh
      ref={mesh}
      position={[placement.x, 0.03, placement.z]}
      rotation={[-Math.PI / 2, 0, 0]}
    >
      <ringGeometry args={[0.7, 0.82, 32]} />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.8}
        depthWrite={false}
      />
    </mesh>
  );
}

function Scene({
  cameras,
  layout,
  selectedId,
  onSelect,
  alertLevels,
  pings,
  palette,
  onDecline,
}: {
  cameras: Camera[];
  layout: CameraLayout;
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  alertLevels: Record<number, string>;
  pings: SitePing[];
  palette: Palette;
  onDecline: () => void;
}) {
  const invalidate = useThree((state) => state.invalidate);

  useEffect(() => {
    invalidate();
  }, [selectedId, pings, alertLevels, invalidate]);

  return (
    <>
      <ambientLight intensity={0.75} />
      <directionalLight position={[10, 15, 8]} intensity={1.05} />
      <PerformanceMonitor onDecline={onDecline} />
      <Controls />
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.01, 0]}
        onClick={() => onSelect(null)}
      >
        <planeGeometry args={[40, 40]} />
        <meshStandardMaterial color={palette.ground} roughness={1} />
      </mesh>
      <gridHelper
        args={[40, 20, palette.grid, palette.grid]}
        position={[0, 0.005, 0]}
      />
      {cameras.map((camera) => {
        const placement = layout[camera.id];
        if (!placement) return null;
        return (
          <CameraNode
            key={camera.id}
            camera={camera}
            placement={placement}
            selected={camera.id === selectedId}
            alert={alertLevels[camera.id]}
            palette={palette}
            onSelect={onSelect}
          />
        );
      })}
      {pings.map((ping) => {
        const placement = layout[ping.cameraId];
        if (!placement) return null;
        return (
          <PingRing
            key={`${ping.id}-${ping.cameraId}`}
            placement={placement}
            color={severityColor(ping.severity, palette)}
          />
        );
      })}
    </>
  );
}

function Controls() {
  const invalidate = useThree((state) => state.invalidate);
  const ref = useRef<OrbitControlsImpl>(null);

  return (
    <OrbitControls
      ref={ref}
      enableDamping={false}
      enablePan
      maxPolarAngle={Math.PI / 2.2}
      minDistance={8}
      maxDistance={48}
      onChange={() => {
        const target = ref.current?.target;
        if (target) {
          target.x = Math.max(-16, Math.min(16, target.x));
          target.z = Math.max(-16, Math.min(16, target.z));
        }
        invalidate();
      }}
    />
  );
}

export function SiteTwin3D({
  cameras,
  layout,
  selectedId,
  onSelect,
  alertLevels,
  pings,
  listId,
  onFallback,
}: SiteTwin3DProps) {
  const palette = usePalette();
  const coarse =
    typeof window !== "undefined" &&
    window.matchMedia("(pointer: coarse)").matches;
  const declines = useRef(0);

  return (
    <div
      className="relative h-full w-full"
      aria-hidden="true"
      aria-describedby={listId}
    >
      <Canvas
        frameloop="demand"
        dpr={[1, 1.5]}
        performance={{ min: 0.5 }}
        camera={{ fov: 35, position: [15, 13, 15], near: 0.1, far: 200 }}
        gl={{
          antialias: !coarse,
          powerPreference: "high-performance",
        }}
        onCreated={({ gl }) => {
          gl.domElement.addEventListener(
            "webglcontextlost",
            (event) => {
              event.preventDefault();
              onFallback("context");
            },
            { once: true },
          );
        }}
      >
        <Scene
          cameras={cameras}
          layout={layout}
          selectedId={selectedId}
          onSelect={onSelect}
          alertLevels={alertLevels}
          pings={pings}
          palette={palette}
          onDecline={() => {
            declines.current += 1;
            if (declines.current >= 2) onFallback("performance");
          }}
        />
      </Canvas>
    </div>
  );
}
