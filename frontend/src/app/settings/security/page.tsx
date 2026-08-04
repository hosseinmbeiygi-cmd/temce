"use client";

import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { KeyRound, ShieldCheck, ShieldOff, Copy, Check, Smartphone, Mail, Send } from "lucide-react";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

// ── Types ───────────────────────────────────────────────────────

type MfaMethod = "totp" | "email" | "telegram";

interface MfaStatus {
  enabled: boolean;
  pending: boolean;
  method: MfaMethod | null;
  telegram_chat_id?: string | null;
}

interface SetupResponse {
  method: MfaMethod;
  secret?: string;
  uri?: string;
  pending?: boolean;
  delivered_to?: string;
}

interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: { message?: string };
  message?: string;
}

const METHOD_META: Record<
  MfaMethod,
  { label: string; description: string; icon: typeof Smartphone }
> = {
  totp: {
    label: "برنامه احراز هویت",
    description: "Google Authenticator یا برنامه‌های مشابه — کد ۶ رقمی هر ۳۰ ثانیه",
    icon: Smartphone,
  },
  email: {
    label: "ایمیل",
    description: "دریافت کد یک‌بارمصرف در ایمیل شما",
    icon: Mail,
  },
  telegram: {
    label: "تلگرام",
    description: "دریافت کد یک‌بارمصرف در تلگرام",
    icon: Send,
  },
};

function methodLabel(method: MfaMethod | null | undefined): string {
  if (!method) return "—";
  return METHOD_META[method]?.label ?? method;
}

// ── Page ────────────────────────────────────────────────────────

export default function SecuritySettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  // MFA status
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["mfa", "status"],
    queryFn: async () => {
      const res = await apiGet<ApiEnvelope<MfaStatus>>("/auth/mfa/status");
      return res.data ?? { enabled: false, pending: false, method: null };
    },
    enabled: !!user,
  });

  const refreshStatus = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["mfa", "status"] });
  }, [queryClient]);

  // ── Enable flow state ──
  const [enabledMethod, setEnabledMethod] = useState<MfaMethod>("totp");
  const [password, setPassword] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [setupResult, setSetupResult] = useState<SetupResponse | null>(null);
  const [code, setCode] = useState("");
  const [copied, setCopied] = useState(false);

  // Pre-fill the saved per-user Telegram chat ID when it exists.
  // Sync from an async query result — the documented pattern for this.
  const savedTelegramChatId = status?.telegram_chat_id;
  useEffect(() => {
    if (savedTelegramChatId && !telegramChatId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTelegramChatId(savedTelegramChatId);
    }
  }, [savedTelegramChatId, telegramChatId]);

  // ── Disable flow state ──
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [disableSent, setDisableSent] = useState(false);

  // ── Mutations ──

  const setupMutation = useMutation({
    mutationFn: async (method: MfaMethod) => {
      const res = await apiPost<ApiEnvelope<SetupResponse>>("/auth/mfa/setup", {
        password,
        method,
        telegram_chat_id: method === "telegram" ? telegramChatId.trim() : "",
      });
      if (!res.success) {
        throw new Error(res.error?.message ?? "شروع فعال‌سازی ناموفق بود");
      }
      return res.data!;
    },
    onSuccess: (data) => {
      setSetupResult(data);
      setCode("");
      toast.success(
        data.method === "totp"
          ? "کد QR ساخته شد — آن را اسکن کنید"
          : `کد تأیید به ${data.delivered_to === "email" ? "ایمیل" : "تلگرام"} ارسال شد`,
      );
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const confirmMutation = useMutation({
    mutationFn: async () => {
      const res = await apiPost<ApiEnvelope<{ enabled: boolean }>>("/auth/mfa/confirm", {
        code,
      });
      if (!res.success) {
        throw new Error(res.error?.message ?? "کد نامعتبر است");
      }
      return res.data!;
    },
    onSuccess: () => {
      toast.success("احراز هویت دومرحله‌ای فعال شد 🎉");
      setSetupResult(null);
      setPassword("");
      setCode("");
      setEnabledMethod("totp");
      refreshStatus();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const disableSendMutation = useMutation({
    mutationFn: async () => {
      const res = await apiPost<ApiEnvelope<{ requires_code: boolean }>>("/auth/mfa/disable", {
        password: disablePassword,
        code: "",
        send_code: true,
      });
      if (!res.success) {
        throw new Error(res.error?.message ?? "ارسال کد ناموفق بود");
      }
      return res.data!;
    },
    onSuccess: () => {
      setDisableSent(true);
      toast.success("کد تأیید ارسال شد — آن را در کادر زیر وارد کنید");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const disableConfirmMutation = useMutation({
    mutationFn: async () => {
      const res = await apiPost<ApiEnvelope<{ enabled: boolean }>>("/auth/mfa/disable", {
        password: disablePassword,
        code: disableCode,
        send_code: false,
      });
      if (!res.success) {
        throw new Error(res.error?.message ?? "کد نامعتبر است");
      }
      return res.data!;
    },
    onSuccess: () => {
      toast.success("احراز هویت دومرحله‌ای غیرفعال شد");
      setDisablePassword("");
      setDisableCode("");
      setDisableSent(false);
      refreshStatus();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const copyUri = useCallback(async () => {
    if (!setupResult?.uri) return;
    try {
      await navigator.clipboard.writeText(setupResult.uri);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.info("کپی دستی: متن otpauth را از باکس پایین بردارید");
    }
  }, [setupResult]);

  const resetSetup = useCallback(() => {
    setSetupResult(null);
    setCode("");
    setPassword("");
    setTelegramChatId("");
  }, []);

  const cancelDisable = useCallback(() => {
    setDisablePassword("");
    setDisableCode("");
    setDisableSent(false);
  }, []);

  const mfaEnabled = status?.enabled ?? false;
  const activeMethod = status?.method ?? "totp";

  // ── Render ──

  return (
    <AppLayout title="امنیت حساب" subtitle="احراز هویت دومرحله‌ای (MFA)">
      <div className="flex flex-col gap-6 max-w-3xl">
        {/* ── Status header ── */}
        <Card
          title="وضعیت احراز هویت دومرحله‌ای"
          subtitle="با فعال‌سازی MFA، علاوه بر رمز عبور، یک کد یک‌بارمصرف برای ورود لازم است"
        >
          {statusLoading ? (
            <Skeleton className="h-16" />
          ) : (
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-4">
                {mfaEnabled ? (
                  <div className="w-12 h-12 rounded-2xl bg-emerald-500/15 flex items-center justify-center">
                    <ShieldCheck className="w-6 h-6 text-emerald-400" />
                  </div>
                ) : (
                  <div className="w-12 h-12 rounded-2xl bg-surface-700/40 flex items-center justify-center">
                    <ShieldOff className="w-6 h-6 text-surface-400" />
                  </div>
                )}
                <div>
                  <div className="text-lg font-semibold">
                    {mfaEnabled ? "فعال" : "غیرفعال"}
                  </div>
                  {mfaEnabled && (
                    <div className="text-sm text-surface-400">
                      روش: {methodLabel(activeMethod)}
                    </div>
                  )}
                  {status?.pending && !mfaEnabled && (
                    <div className="text-sm text-amber-400">
                      فعال‌سازی ناتمام — مراحل زیر را کامل کنید
                    </div>
                  )}
                </div>
              </div>
              {mfaEnabled && (
                <span className="text-xs px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-400">
                  امنیت بالا
                </span>
              )}
            </div>
          )}
        </Card>

        {/* ── Enable flow (when MFA is OFF) ── */}
        {!mfaEnabled && (
          <Card
            title="فعال‌سازی"
            subtitle="روش دریافت کد را انتخاب کنید و مراحل را دنبال کنید"
          >
            {/* Step 1: method + password */}
            {!setupResult && (
              <div className="flex flex-col gap-5">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {(Object.keys(METHOD_META) as MfaMethod[]).map((m) => {
                    const Icon = METHOD_META[m].icon;
                    const selected = enabledMethod === m;
                    return (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setEnabledMethod(m)}
                        className={`p-4 rounded-2xl border text-right transition-all cursor-pointer ${
                          selected
                            ? "border-primary-500 bg-primary-500/10 ring-1 ring-primary-500/40"
                            : "border-surface-700 bg-surface-800/40 hover:border-surface-600"
                        }`}
                      >
                        <Icon className="w-5 h-5 mb-3 text-primary-400" />
                        <div className="text-sm font-medium">{METHOD_META[m].label}</div>
                        <div className="text-xs text-surface-400 mt-1 leading-relaxed">
                          {METHOD_META[m].description}
                        </div>
                      </button>
                    );
                  })}
                </div>

                {enabledMethod === "telegram" && (
                  <div>
                    <label className="block text-sm text-surface-300 mb-2">
                      آیدی عددی چت تلگرام شما <span className="text-rose-400">*</span>
                    </label>
                    <input
                      type="text"
                      value={telegramChatId}
                      onChange={(e) => setTelegramChatId(e.target.value.replace(/\s/g, ""))}
                      placeholder="مثلاً 123456789"
                      className="w-full px-4 py-3 rounded-xl bg-surface-800 border border-surface-700 text-sm focus:border-primary-500 focus:outline-none"
                    />
                    <p className="text-xs text-surface-500 mt-1.5 leading-relaxed">
                      با بات خود در تلگرام گفتگو کنید و از <b>@userinfobot</b> آیدی عددی را
                      بگیرید — کدها به همین چت ارسال می‌شوند.
                    </p>
                  </div>
                )}

                <div>
                  <label className="block text-sm text-surface-300 mb-2">
                    رمز عبور فعلی <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="برای تأیید هویت، رمز عبور خود را وارد کنید"
                    className="w-full px-4 py-3 rounded-xl bg-surface-800 border border-surface-700 text-sm focus:border-primary-500 focus:outline-none"
                  />
                </div>

                <button
                  type="button"
                  disabled={
                    !password ||
                    (enabledMethod === "telegram" && !telegramChatId.trim()) ||
                    setupMutation.isPending
                  }
                  onClick={() => setupMutation.mutate(enabledMethod)}
                  className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-primary-600 text-white text-sm font-semibold hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors self-start"
                >
                  <KeyRound className="w-4 h-4" />
                  {setupMutation.isPending ? "در حال ارسال…" : "مرحله بعد"}
                </button>
              </div>
            )}

            {/* Step 2: QR (totp) or delivered code (email/telegram) + confirm */}
            {setupResult && (
              <div className="flex flex-col gap-5">
                {setupResult.method === "totp" && (
                  <div className="text-xs text-surface-500">
                    رمز عبور قبلاً تأیید شد — این مرحله فقط کد برنامه احراز هویت را می‌پذیرد.
                  </div>
                )}

                {setupResult.method === "totp" ? (
                  <div className="flex flex-col sm:flex-row items-center gap-6">
                    <div className="p-3 bg-white rounded-2xl shrink-0">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(
                          setupResult.uri ?? "",
                        )}`}
                        alt="کد QR احراز هویت"
                        width={180}
                        height={180}
                        referrerPolicy="no-referrer"
                        className="rounded-xl"
                      />
                    </div>
                    <div className="flex flex-col gap-3 text-sm text-surface-300">
                      <p>
                        ۱. اپلیکیشن احراز هویت را باز کنید (Google Authenticator و…)
                      </p>
                      <p>۲. با اسکن این QR یا کپی کردن متن otpauth، حساب را اضافه کنید</p>
                      <button
                        type="button"
                        onClick={copyUri}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-800 border border-surface-700 text-xs hover:border-surface-600 transition-colors self-start cursor-pointer"
                      >
                        {copied ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                        {copied ? "کپی شد!" : "کپی متن otpauth"}
                      </button>
                      {setupResult.secret && (
                        <p className="text-xs text-surface-500 break-all font-mono">
                          کلید مخفی: {setupResult.secret}
                        </p>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded-xl bg-primary-500/10 border border-primary-500/30 text-sm text-surface-200 leading-relaxed">
                    یک کد ۶ رقمی به{" "}
                    <b>{setupResult.delivered_to === "email" ? "ایمیل شما" : "تلگرام شما"}</b>{" "}
                    ارسال شد. کد را در کادر زیر وارد کنید (تا ۵ دقیقه معتبر است).
                  </div>
                )}

                <div>
                  <label className="block text-sm text-surface-300 mb-2">
                    کد تأیید (۶ رقم)
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="۱۲۳۴۵۶"
                    className="w-full px-4 py-3 rounded-xl bg-surface-800 border border-surface-700 text-sm text-center tracking-[0.5em] font-mono focus:border-primary-500 focus:outline-none"
                  />
                </div>

                <div className="flex items-center gap-3 flex-wrap">
                  <button
                    type="button"
                    disabled={code.length !== 6 || confirmMutation.isPending}
                    onClick={() => confirmMutation.mutate()}
                    className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-primary-600 text-white text-sm font-semibold hover:bg-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ShieldCheck className="w-4 h-4" />
                    {confirmMutation.isPending ? "در حال تأیید…" : "تأیید و فعال‌سازی"}
                  </button>
                  {setupResult.method !== "totp" && (
                    <button
                      type="button"
                      disabled={setupMutation.isPending}
                      onClick={() => setupMutation.mutate(setupResult.method)}
                      className="inline-flex items-center gap-2 px-4 py-3 rounded-xl bg-surface-800 border border-surface-700 text-sm text-surface-200 hover:border-surface-600 disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      <Send className="w-4 h-4" />
                      {setupMutation.isPending ? "در حال ارسال…" : "ارسال مجدد کد"}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={resetSetup}
                    className="px-4 py-3 rounded-xl text-sm text-surface-400 hover:text-surface-200 transition-colors cursor-pointer"
                  >
                    انصراف
                  </button>
                </div>
              </div>
            )}
          </Card>
        )}

        {/* ── Disable flow (when MFA is ON) ── */}
        {mfaEnabled && (
          <Card
            title="غیرفعال‌سازی"
            subtitle="برای غیرفعال‌کردن MFA، رمز عبور و کد تأیید لازم است"
          >
            <div className="flex flex-col gap-4">
              <div>
                <label className="block text-sm text-surface-300 mb-2">رمز عبور فعلی</label>
                <input
                  type="password"
                  value={disablePassword}
                  onChange={(e) => setDisablePassword(e.target.value)}
                  placeholder="رمز عبور خود را وارد کنید"
                  className="w-full px-4 py-3 rounded-xl bg-surface-800 border border-surface-700 text-sm focus:border-primary-500 focus:outline-none"
                />
              </div>

              <div className="flex flex-col gap-3">
                {activeMethod !== "totp" && (
                  <button
                    type="button"
                    disabled={!disablePassword || disableSendMutation.isPending}
                    onClick={() => disableSendMutation.mutate()}
                    className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-surface-800 border border-surface-700 text-sm font-medium hover:border-surface-600 disabled:opacity-50 transition-colors self-start cursor-pointer"
                  >
                    <Send className="w-4 h-4" />
                    {disableSendMutation.isPending
                      ? "در حال ارسال…"
                      : disableSent
                        ? "ارسال مجدد کد"
                        : "ارسال کد تأیید"}
                  </button>
                )}

                {activeMethod === "totp" && (
                  <p className="text-xs text-surface-400">
                    برای غیرفعال‌سازی، کد فعلی اپلیکیشن احراز هویت را وارد کنید.
                  </p>
                )}

                {disableSent && (
                  <p className="text-sm text-emerald-400 flex items-center gap-2">
                    <Check className="w-4 h-4" /> کد ارسال شد — آن را در کادر زیر وارد کرده و
                    «غیرفعال‌کردن MFA» را بزنید.
                  </p>
                )}

                <div>
                  <label className="block text-sm text-surface-300 mb-2">
                    کد تأیید (۶ رقم)
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={disableCode}
                    onChange={(e) =>
                      setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))
                    }
                    placeholder="۱۲۳۴۵۶"
                    className="w-full px-4 py-3 rounded-xl bg-surface-800 border border-surface-700 text-sm text-center tracking-[0.5em] font-mono focus:border-rose-500 focus:outline-none"
                  />
                </div>

                <div className="flex items-center gap-3 flex-wrap">
                  <button
                    type="button"
                    disabled={!disablePassword || disableCode.length !== 6 || disableConfirmMutation.isPending}
                    onClick={() => disableConfirmMutation.mutate()}
                    className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-rose-600 text-white text-sm font-semibold hover:bg-rose-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ShieldOff className="w-4 h-4" />
                    {disableConfirmMutation.isPending ? "در حال غیرفعال‌سازی…" : "غیرفعال‌کردن MFA"}
                  </button>
                  <button
                    type="button"
                    onClick={cancelDisable}
                    className="px-4 py-3 rounded-xl text-sm text-surface-400 hover:text-surface-200 transition-colors cursor-pointer"
                  >
                    انصراف
                  </button>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* ── Info note ── */}
        <div className="text-xs text-surface-500 leading-relaxed bg-surface-800/40 border border-surface-800 rounded-xl p-4">
          💡 <b>راهنما:</b> پس از فعال‌سازی، در مرحله ورود علاوه بر رمز عبور، کد یک‌بارمصرف هم
          درخواست می‌شود. کدها تا ۵ دقیقه معتبر هستند و هر کد فقط یک‌بار قابل استفاده است.
          اگر به برنامه احراز هویت دسترسی ندارید، روش «ایمیل» یا «تلگرام» را انتخاب کنید.
        </div>
      </div>
    </AppLayout>
  );
}
