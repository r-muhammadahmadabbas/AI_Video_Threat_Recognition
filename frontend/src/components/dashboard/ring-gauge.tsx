"use client";

export function RingGauge({
  value,
  total,
  label,
}: {
  value: number;
  total: number;
  label: string;
}) {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const ratio = total > 0 ? Math.min(1, value / total) : 0;

  return (
    <svg
      width="44"
      height="44"
      viewBox="0 0 44 44"
      role="img"
      aria-label={label}
      className="shrink-0"
    >
      <circle
        cx="22"
        cy="22"
        r={radius}
        fill="none"
        stroke="var(--surface-3)"
        strokeWidth="5"
      />
      <circle
        cx="22"
        cy="22"
        r={radius}
        fill="none"
        stroke="var(--ok)"
        strokeWidth="5"
        strokeLinecap="round"
        strokeDasharray={`${circumference * ratio} ${circumference}`}
        transform="rotate(-90 22 22)"
      />
    </svg>
  );
}
