"use client";

export function Sparkline({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const width = 120;
  const height = 28;
  const max = Math.max(1, ...values);
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((value, index) => {
    const x = index * step;
    const y = height - (value / max) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const line = points.join(" ");
  const area = `0,${height} ${line} ${width},${height}`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="mt-auto h-7 w-full"
      aria-hidden="true"
      preserveAspectRatio="none"
    >
      <polygon points={area} fill="var(--primary)" opacity="0.12" />
      <polyline
        points={line}
        fill="none"
        stroke="var(--primary)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
