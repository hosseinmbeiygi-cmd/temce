"use client";

import { useMemo } from "react";

interface MiniSparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  positiveColor?: string;
  negativeColor?: string;
}

export default function MiniSparkline({
  data,
  width = 80,
  height = 28,
  positiveColor = "#22c55e",
  negativeColor = "#ef4444",
}: MiniSparklineProps) {
  const { points, color } = useMemo(() => {
    if (!data || data.length < 2)
      return { points: "", color: positiveColor };

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const pts = data
      .map(
        (v, i) =>
          `${((i / (data.length - 1)) * width).toFixed(1)},${(
            height -
            (((v - min) / range) * height)
          ).toFixed(1)}`
      )
      .join(" ");
    const trendColor =
      data[data.length - 1] >= data[0] ? positiveColor : negativeColor;
    return { points: pts, color: trendColor };
  }, [data, width, height, positiveColor, negativeColor]);

  if (!points) return null;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="shrink-0"
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
