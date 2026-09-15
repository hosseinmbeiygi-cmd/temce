"use client";
import React from "react";
import type { AlertEvent } from "@/types/gold";
import { ackAlert } from "@/lib/goldApi";

interface Props {
  events: AlertEvent[];
  onAck?: () => void;
  className?: string;
}

export function AlertEventList({ events, onAck, className = "" }: Props) {
  if (events.length === 0) {
    return <div className={`text-zinc-500 text-sm ${className}`}>رویدادی ثبت نشده</div>;
  }

  const handleAck = async (id: number) => {
    await ackAlert(id);
    onAck?.();
  };

  return (
    <div className={`space-y-2 ${className}`}>
      {events.map((e) => (
        <div
          key={e.id}
          className={`p-3 rounded border ${
            e.read_at
              ? "border-zinc-800 bg-zinc-900/50 opacity-60"
              : "border-amber-700 bg-amber-950/30"
          }`}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="text-sm font-semibold text-zinc-100">{e.rule_name}</div>
              <div className="text-xs text-zinc-400 mt-0.5">{e.message}</div>
              <div className="text-[10px] text-zinc-500 mt-1">
                {e.sent_at && new Date(e.sent_at).toLocaleString("fa-IR")} • {e.channel}
              </div>
            </div>
            {!e.read_at && (
              <button
                onClick={() => handleAck(e.id)}
                className="text-xs text-amber-400 hover:text-amber-300 px-2 py-1"
              >
                خواندم
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
