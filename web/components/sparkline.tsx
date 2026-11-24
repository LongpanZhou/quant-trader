import { downsample } from "@/lib/format";

export function Sparkline({
  values,
  color,
  id,
  width = 320,
  height = 78,
}: {
  values: number[];
  color: string;
  id: string;
  width?: number;
  height?: number;
}) {
  const points = downsample(values, 90);
  if (points.length < 2) {
    return <div className="h-[78px] rounded-lg bg-white/[0.02]" />;
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const pad = 4;
  const xy = points.map((value, index) => {
    const x = pad + (index / (points.length - 1)) * (width - pad * 2);
    const y = height - pad - ((value - min) / range) * (height - pad * 2);
    return [x, y] as const;
  });
  const line = xy.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${xy[xy.length - 1][0].toFixed(1)},${height - pad} L${xy[0][0].toFixed(1)},${height - pad} Z`;
  const gradientId = `spark-${id.replace(/[^a-z0-9-]/gi, "")}`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-[78px] w-full"
      preserveAspectRatio="none"
      role="img"
      aria-label="Equity curve sparkline"
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.22} />
          <stop offset="100%" stopColor={color} stopOpacity={0.01} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path d={line} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" />
    </svg>
  );
}
