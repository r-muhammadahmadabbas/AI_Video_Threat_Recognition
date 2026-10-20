import type { ReactNode, SVGProps } from "react";

export type ThreatIconComponent = (props: SVGProps<SVGSVGElement>) => ReactNode;

function Base({
  children,
  ...props
}: SVGProps<SVGSVGElement> & { children?: ReactNode }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export function FirearmIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M2.5 7.5H15l2 .75v1.75l-2 .75h-2.5l-1.25 2.5H8.25L7 10.75H2.5z" />
      <path d="M8.5 13.25 7 16.5" />
      <path d="M5.5 7.5v2" />
    </Base>
  );
}

export function BladeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M4.25 15.5 14 4.5l2.25 2.25-8.5 9.25z" />
      <path d="M4.25 15.5 3 16.75a1.06 1.06 0 0 0 1.5 1.5L5.75 17" />
    </Base>
  );
}

export function ExplosiveIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="8.25" cy="11.75" r="5" />
      <path d="M12.25 7.75c1.25-.5 2.5-.35 3.5-1.75" />
      <path d="M15.75 3.5v-2M17.9 6.1l1.85-.75M16.9 4.6l1.35-1.85" />
    </Base>
  );
}

export function BluntIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="13" cy="7" r="4.25" />
      <path d="M10.4 10.25 3.25 17.25" />
      <path d="M5.9 14.6l1.5 1.5" />
    </Base>
  );
}

export function FireSmokeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M10 2.5s4.5 4.1 4.5 8a4.5 4.5 0 0 1-9 0c0-1.5.75-2.85 1.5-3.6.3 1 .85 1.75 1.6 2.1 0-2.4 1.4-5 1.4-6.5z" />
    </Base>
  );
}

export function ToolIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M14.6 2.6a4.75 4.75 0 0 0-5.75 5.75L2.6 14.6a1.98 1.98 0 1 0 2.8 2.8l6.25-6.25a4.75 4.75 0 0 0 5.75-5.75l-2.5 2.5-2.75-.4-.4-2.75z" />
    </Base>
  );
}

export function PersonDownIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="4.5" cy="12.75" r="2" />
      <path d="M6.75 12.75h7.5" />
      <path d="M14.25 12.75 17.25 10" />
      <path d="M14.25 12.75 17.25 15.75" />
      <path d="M9.75 12.75 7 16" />
    </Base>
  );
}

export function FightIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="5.25" cy="5.5" r="1.9" />
      <path d="M2.25 13.75c0-2.1 1.35-3.5 3-3.5s3 1.4 3 3.5" />
      <circle cx="14.75" cy="5.5" r="1.9" />
      <path d="M11.75 13.75c0-2.1 1.35-3.5 3-3.5s3 1.4 3 3.5" />
      <path d="M8.75 8.75h2.5l-1.5 2.5h2" />
    </Base>
  );
}

export function CrowdIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="4" cy="6.75" r="1.6" />
      <path d="M1.25 14.5c0-1.9 1.2-3.1 2.75-3.1s2.75 1.2 2.75 3.1" />
      <circle cx="10" cy="5.25" r="1.9" />
      <path d="M6.9 14.5c0-2.1 1.35-3.5 3.1-3.5s3.1 1.4 3.1 3.5" />
      <circle cx="16" cy="6.75" r="1.6" />
      <path d="M12.75 14.5c0-1.9 1.2-3.1 2.75-3.1s2.75 1.2 2.75 3.1" />
    </Base>
  );
}

export function ZoneBreachIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <path d="M13.25 2.5v15" strokeDasharray="2.6 2.6" />
      <circle cx="6.25" cy="5.5" r="1.9" />
      <path d="M3.25 13.75c0-2.1 1.35-3.5 3-3.5 1.35 0 2.5.9 2.9 2.25" />
      <path d="M16 9.75h2.25m0 0-1.5-1.5m1.5 1.5-1.5 1.5" />
    </Base>
  );
}

export function LoiterIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Base {...props}>
      <circle cx="7.75" cy="6.75" r="1.9" />
      <path d="M4.75 15.5c0-2.1 1.35-3.5 3-3.5s3 1.4 3 3.5" />
      <path d="M13.75 3.75a6.4 6.4 0 0 1 3.1 4.6" />
      <path d="M16.5 6.5l.35 1.95 1.95-.4" />
    </Base>
  );
}
