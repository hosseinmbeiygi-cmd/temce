"use client";

interface MiniSparklineSignalProps {
  points: number[];
  color?: string;
  label?: string;
  height?: number;
  className?: string;
}

export function MiniSparklineSignal({ points, color, label, height = 22, className = "" }: MiniSparklineSignalProps) {
  if (points.length < 2) return null;

  const width = Math.min(points.length * 8, 120);
  const pad = 1;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const first = points[0];
  const last = points[points.length - 1];
  const trend = last > first ? "up" : last < first ? "down" : "flat";

  const strokeColor = color || (trend === "up" ? "#10b981" : trend === "down" ? "#f43f5e" : "#f59e0b");

  const pointsStr = points
    .map((v, i) => {
      const x = pad + (i / (points.length - 1)) * (width - 2 * pad);
      const y = pad + ((max - v) / range) * (height - 2 * pad);
      return `${x},${y}`;
    })
    .join(" ");

  const areaPath = `${pointsStr} ${width - pad},${height - pad} ${pad},${height - pad}`;

  const tooltip = label
    ? `${label}: ${last.toLocaleString("fa-IR")} • روند: ${trend === "up" ? "صعودی" : trend === "down" ? "نزولی" : "ثابت"}`
    : `دقت: ${last.toFixed(0)}% • روند: ${trend === "up" ? "صعودی" : trend === "down" ? "نزولی" : "ثابت"}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={`shrink-0 ${className}`}
    >
      <title>{tooltip}</title>
      <polygon points={areaPath} fill={strokeColor} fillOpacity="0.12" />
      <polyline points={pointsStr} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
