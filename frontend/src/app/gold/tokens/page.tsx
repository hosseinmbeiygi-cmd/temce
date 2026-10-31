"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createApiToken, getApiTokens, revokeApiToken } from "@/lib/goldApi";
import { ConfirmDialog } from "@/components/gold/ConfirmDialog";
import type { GoldApiToken } from "@/lib/goldApi";

export default function GoldTokensPage() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState("read");
  const [newToken, setNewToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingRevoke, setPendingRevoke] = useState<GoldApiToken | null>(null);
  const [adminAck, setAdminAck] = useState(false);

  const { data: tokens, isError } = useQuery({
    queryKey: ["gold", "tokens"],
    queryFn: getApiTokens,
    refetchInterval: 30_000,
  });

  const onCreate = async () => {
    if (!name.trim()) return;
    if (scopes === "admin" && !adminAck) {
      setError("برای ساخت token با scope ادمین، تأیید دسترسی کامل را بزنید.");
      return;
    }
    setError(null);
    try {
      const r = await createApiToken(name.trim(), scopes);
      setNewToken(r.token);
      setName("");
      qc.invalidateQueries({ queryKey: ["gold", "tokens"] });
    } catch (err) {
      // مسیر قبلاً بدون catch بود: یک 400 (scopes نامعتبر) بی‌سروصدا می‌مرد و
      // کاربر فکر می‌کرد token ساخته شده.
      setError(err instanceof Error ? err.message : "ساخت token ناموفق بود.");
    }
  };

  const confirmRevoke = async () => {
    if (!pendingRevoke) return;
    try {
      await revokeApiToken(pendingRevoke.token_id);
      qc.invalidateQueries({ queryKey: ["gold", "tokens"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "لغو token ناموفق بود.");
    } finally {
      setPendingRevoke(null);
    }
  };

  const copyToken = () => {
    if (newToken) {
      void navigator.clipboard.writeText(newToken).catch(() => {
        setError("کپی خودکار ممکن نشد؛ token را دستی انتخاب و کپی کنید.");
      });
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
        {scopes === "admin" && (
          <label className="flex items-start gap-2 rounded-lg px-3 py-2 text-[11px]" style={{ background: "var(--gd-bg-3)", color: "var(--gd-warning, #f59e0b)" }}>
            <input type="checkbox" checked={adminAck} onChange={(e) => setAdminAck(e.target.checked)} className="mt-0.5" />
            می‌دانم scope ادمین اجازهٔ مدیریت tokenها و همهٔ نوشتن‌ها را می‌دهد.
          </label>
        )}
        <button
          onClick={onCreate}
          disabled={!name.trim() || (scopes === "admin" && !adminAck)}
          className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-700 text-white rounded px-3 py-2 text-sm font-semibold"
        >
          ساخت Token
        </button>
        {error && (
          <div className="rounded-lg px-3 py-2 text-xs" style={{ background: "var(--gd-bg-3)", color: "var(--gd-danger)" }}>
            {error}
          </div>
        )}
      </div>

      {isError && (
        <div className="rounded-lg px-3 py-2 text-xs" style={{ background: "var(--gd-bg-3)", color: "var(--gd-danger)" }}>
          دریافت لیست tokenها ناموفق بود؛ لیست زیر معتبر نیست.
        </div>
      )}

      <div className="rounded-xl overflow-hidden" style={{ background: "var(--gd-bg-2)", border: "1px solid var(--gd-border)" }}>
        <div className="px-4 py-3 text-sm font-semibold" style={{ color: "var(--gd-text)" }}>
          Tokenهای فعال ({tokens ? tokens.filter((t) => t.enabled).length : "—"})
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
                  <button
                    onClick={() => setPendingRevoke(t)}
                    className="text-xs hover:underline"
                    style={{ color: "var(--gd-danger)" }}
                    aria-label={`لغو token ${t.name}`}
                  >
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
        <code className="block bg-zinc-950 p-2 rounded font-mono text-emerald-300" dir="ltr">
          curl -H &quot;Authorization: Bearer YOUR_TOKEN&quot; &lt;YOUR_HOST&gt;/api/v1/gold/snapshot
        </code>
        <div>لیست کامل endpointها: <code className="text-amber-400">/api/v1/gold/docs/endpoints</code></div>
      </div>

      <ConfirmDialog
        open={pendingRevoke !== null}
        title={`لغو token «${pendingRevoke?.name ?? ""}»؟`}
        description={
          <>
            هر ابزار خارجی که با این token کار می‌کند (ربات تلگرام، Google Sheets،
            اپ موبایل) از همین لحظه unauthorized می‌شود.
            <div className="mt-2">
              token های لغوشده قابل بازگردانی نیستند؛ برای ادامه باید یک token تازه
              ساخته و در آن ابزار جایگزین شود.
            </div>
          </>
        }
        confirmLabel="لغو token"
        onConfirm={confirmRevoke}
        onCancel={() => setPendingRevoke(null)}
      />
    </div>
  );
}
