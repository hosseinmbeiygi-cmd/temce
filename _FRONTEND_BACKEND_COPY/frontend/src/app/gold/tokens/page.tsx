"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

interface Token {
  token_id: string;
  name: string;
  scopes: string[];
  enabled: boolean;
  created_at: string | null;
  last_used_at: string | null;
}

async function listTokens(): Promise<Token[]> {
  const r = await fetch("/api/gold/tokens", { credentials: "include" });
  const j = await r.json();
  return j.data ?? [];
}

async function createToken(name: string, scopes: string): Promise<{ token: string; token_id: string }> {
  const r = await fetch(`/api/gold/tokens?name=${encodeURIComponent(name)}&scopes=${encodeURIComponent(scopes)}`, {
    method: "POST",
    credentials: "include",
  });
  const j = await r.json();
  return j.data;
}

async function revokeToken(tokenId: string): Promise<boolean> {
  const r = await fetch(`/api/gold/tokens/${tokenId}`, { method: "DELETE", credentials: "include" });
  const j = await r.json();
  return j.success;
}

export default function GoldTokensPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState("read");
  const [newToken, setNewToken] = useState<string | null>(null);

  const { data: tokens } = useQuery({ queryKey: ["gold", "tokens"], queryFn: listTokens, refetchInterval: 30_000 });

  const onCreate = async () => {
    if (!name.trim()) return;
    const r = await createToken(name.trim(), scopes);
    setNewToken(r.token);
    setName("");
    qc.invalidateQueries({ queryKey: ["gold", "tokens"] });
  };

  const onRevoke = async (id: string) => {
    if (!confirm("Token لغو شود؟")) return;
    await revokeToken(id);
    qc.invalidateQueries({ queryKey: ["gold", "tokens"] });
  };

  const copyToken = () => {
    if (newToken) {
      navigator.clipboard.writeText(newToken);
    }
  };

  return (
    <div className="max-w-3xl space-y-6" dir="rtl">
      <div className="text-sm" style={{ color: "var(--gd-text-2)" }}>
        برای اتصال ابزارهای خارجی (Google Sheets، ربات تلگرام، اپ موبایل).
        Token فقط یک‌بار نمایش داده می‌شود.
      </div>

      {newToken && (
        <div className="rounded-xl p-4 space-y-2" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
          <div className="text-sm font-semibold text-amber-400">⚠️ Token جدید — ذخیره کنید:</div>
          <code className="block bg-zinc-950 p-3 rounded text-xs text-emerald-300 break-all font-mono">
            {newToken}
          </code>
          <div className="flex gap-2">
            <button onClick={copyToken} className="text-xs bg-emerald-600 hover:bg-emerald-500 text-white rounded px-3 py-1.5">
              کپی
            </button>
            <button onClick={() => setNewToken(null)} className="text-xs bg-zinc-700 hover:bg-zinc-600 text-zinc-200 rounded px-3 py-1.5">
              بستن
            </button>
          </div>
        </div>
      )}

      <div className="rounded-xl p-4 space-y-3" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
        <h3 className="text-sm font-semibold" style={{ color: "var(--gd-text)" }}>ساخت Token جدید</h3>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="نام (مثلاً Telegram Bot)"
          className="w-full px-3 py-2 rounded text-sm"
          style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}
        />
        <select
          value={scopes}
          onChange={(e) => setScopes(e.target.value)}
          className="w-full px-3 py-2 rounded text-sm"
          style={{ background: "var(--gd-bg)", color: "var(--gd-text)", border: "1px solid var(--gd-border)" }}
        >
          <option value="read">read — فقط خواندن</option>
          <option value="write">write — خواندن + نوشتن</option>
          <option value="admin">admin — دسترسی کامل</option>
        </select>
        <button
          onClick={onCreate}
          disabled={!name.trim()}
          className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white rounded px-3 py-2 text-sm font-semibold"
        >
          ساخت Token
        </button>
      </div>

      <div className="rounded-xl overflow-hidden" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
        <div className="px-4 py-3 text-sm font-semibold" style={{ color: "var(--gd-text)" }}>
          Tokenهای فعال ({tokens?.length ?? 0})
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px]" style={{ color: "var(--gd-text-3)" }}>
              <th className="text-right p-3">ID</th>
              <th className="text-right p-3">نام</th>
              <th className="text-right p-3">Scopes</th>
              <th className="text-right p-3">آخرین استفاده</th>
              <th className="text-right p-3">عملیات</th>
            </tr>
          </thead>
          <tbody>
            {(tokens ?? []).map((t) => (
              <tr key={t.token_id} style={{ borderTop: "1px solid var(--gd-border)" }}>
                <td className="p-3 font-mono text-xs" style={{ color: "var(--gd-text-2)" }}>{t.token_id}</td>
                <td className="p-3" style={{ color: "var(--gd-text)" }}>{t.name}</td>
                <td className="p-3">
                  {t.scopes.map((s) => (
                    <span key={s} className="text-[10px] px-2 py-0.5 rounded mr-1" style={{ background: "var(--gd-bg-3)" }}>
                      {s}
                    </span>
                  ))}
                </td>
                <td className="p-3 text-xs" style={{ color: "var(--gd-text-2)" }}>
                  {t.last_used_at ? new Date(t.last_used_at).toLocaleString("fa-IR") : "هرگز"}
                </td>
                <td className="p-3">
                  <button onClick={() => onRevoke(t.token_id)} className="text-xs text-rose-400 hover:text-rose-300">
                    لغو
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-xl p-4 text-xs space-y-2" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)", color: "var(--gd-text-2)" }}>
        <div className="font-semibold" style={{ color: "var(--gd-text)" }}>نحوه استفاده:</div>
        <code className="block bg-zinc-950 p-2 rounded font-mono text-emerald-300">
          curl -H &quot;Authorization: Bearer YOUR_TOKEN&quot; http://localhost:8000/api/gold/snapshot
        </code>
        <div>لیست کامل endpointها: <code className="text-amber-400">/api/gold/docs/endpoints</code></div>
      </div>
    </div>
  );
}
