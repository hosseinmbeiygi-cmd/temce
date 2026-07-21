"use client";

import React from "react";

interface TreemapContentProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  depth?: number;
  name?: string;
  change?: number;
  index?: number;
  root?: { name?: string };
  onMouseEnter?: (e: React.MouseEvent, data: Record<string, unknown>) => void;
  onMouseLeave?: () => void;
  [key: string]: unknown;
}

function getChangeColor(change: number): string {
  const intensity = Math.min(Math.abs(change) / 5, 1);
  if (change > 0) {
    const r = Math.round(5 + (1 - intensity) * 55);
    const g = Math.round(120 + intensity * 77);
    const b = Math.round(60 + (1 - intensity) * 20);
    return `rgb(${r}, ${g}, ${b})`;
  } else if (change < 0) {
    const r = Math.round(180 + intensity * 55);
    const g = Math.round(30 + (1 - intensity) * 30);
    const b = Math.round(40 + (1 - intensity) * 20);
    return `rgb(${r}, ${g}, ${b})`;
  }
  return "rgb(60, 60, 80)";
}

export default function TreemapContent(props: TreemapContentProps) {
  const { x = 0, y = 0, width = 0, height = 0, depth = 0, name = "", change = 0 } = props;

  // Group header (depth 1)
  if (depth === 1) {
    return (
      <g>
        <rect
          x={x}
          y={y}
          width={width}
          height={height}
          style={{
            fill: "rgba(30, 30, 50, 0.85)",
            stroke: "rgba(100, 100, 140, 0.3)",
            strokeWidth: 2,
          }}
        />
        {width > 60 && height > 24 && (
          <text
            x={x + width / 2}
            y={y + 14}
            textAnchor="middle"
            fill="#94a3b8"
            fontSize={width > 120 ? 11 : 9}
            fontWeight={600}
          >
            {name}
          </text>
        )}
      </g>
    );
  }

  // Leaf node (depth 2)
  if (depth === 2 && width > 2 && height > 2) {
    const bgColor = getChangeColor(change);
    const textColor = Math.abs(change) > 2 ? "#ffffff" : "#e2e8f0";
    const showText = width > 30 && height > 20;
    const showChange = width > 40 && height > 32;

    return (
      <g>
        <rect
          x={x + 1}
          y={y + 1}
          width={Math.max(0, width - 2)}
          height={Math.max(0, height - 2)}
          rx={3}
          ry={3}
          style={{
            fill: bgColor,
            stroke: "rgba(0, 0, 0, 0.3)",
            strokeWidth: 1,
            cursor: "pointer",
          }}
        />
        {showText && (
          <text
            x={x + width / 2}
            y={y + height / 2 - (showChange ? 4 : 0)}
            textAnchor="middle"
            fill={textColor}
            fontSize={width > 60 ? 11 : 9}
            fontWeight={700}
            style={{ pointerEvents: "none" }}
          >
            {name}
          </text>
        )}
        {showChange && (
          <text
            x={x + width / 2}
            y={y + height / 2 + 12}
            textAnchor="middle"
            fill={textColor}
            fontSize={9}
            fontWeight={600}
            opacity={0.8}
            style={{ pointerEvents: "none" }}
          >
            {change > 0 ? "+" : ""}{change.toFixed(1)}%
          </text>
        )}
      </g>
    );
  }

  return null;
}
