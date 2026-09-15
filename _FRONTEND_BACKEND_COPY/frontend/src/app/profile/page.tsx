"use client";

import { useState, type FormEvent } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPut, apiPost } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";

interface UserProfile {
  id: string;
  username: string;
  email: string;
  full_name: string;
  phone: string;
  roles: string[];
  is_active: boolean;
  is_verified: boolean;
  last_login: string | null;
  created_at: string | null;
}

interface LoginHistoryItem {
  ip_address: string;
  user_agent: string;
  created_at: string;
}

const ROLE_LABELS: Record<string, { label: string; color: string }> = {
  admin: { label: "ادمین", color: "bg-rose-500/20 text-rose-400" },
  analyst: { label: "تحلیلگر", color: "bg-amber-500/20 text-amber-400" },
  user: { label: "کاربر", color: "bg-emerald-500/20 text-emerald-400" },
  viewer: { label: "بیننده", color: "bg-surface-600/20 text-surface-400" },
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("fa-IR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  // Profile form state
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");

  // Password form state
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // Messages
  const [profileMsg, setProfileMsg] = useState("");
  const [passwordMsg, setPasswordMsg] = useState("");

  // Fetch user profile
  const { data: profile, isLoading } = useQuery<UserProfile>({
    queryKey: ["user-profile"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: UserProfile }>("/auth/me");
      return res.data || res;
    },
    staleTime: 60_000,
  });

  // Sync profile data to form fields once when loaded.
  // React-documented pattern: adjust state during render (guarded by a marker)
  // instead of an effect, to avoid cascading renders after data arrives.
  const [syncedProfileId, setSyncedProfileId] = useState<string | null>(null);
  if (profile && profile.id !== syncedProfileId) {
    setSyncedProfileId(profile.id);
    setFullName(profile.full_name || "");
    setPhone(profile.phone || "");
    setEmail(profile.email || "");
  }

  // Update profile mutation
  const updateProfileMutation = useMutation({
    mutationFn: async () => {
      return apiPut("/auth/profile", {
        full_name: fullName,
        phone: phone,
        email: email,
      });
    },
    onSuccess: () => {
      setProfileMsg("✅ پروفایل با موفقیت به‌روزرسانی شد");
      queryClient.invalidateQueries({ queryKey: ["user-profile"] });
      setTimeout(() => setProfileMsg(""), 3000);
    },
    onError: () => {
      setProfileMsg("❌ خطا در به‌روزرسانی پروفایل");
      setTimeout(() => setProfileMsg(""), 3000);
    },
  });

  // Change password mutation
  const changePasswordMutation = useMutation({
    mutationFn: async () => {
      return apiPost("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
    },
    onSuccess: () => {
      setPasswordMsg("✅ رمز عبور با موفقیت تغییر کرد. لطفاً مجدداً وارد شوید.");
      setTimeout(() => {
        logout();
        router.push("/auth/login");
      }, 2000);
    },
    onError: () => {
      setPasswordMsg("❌ خطا در تغییر رمز عبور. رمز فعلی صحیح نیست.");
      setTimeout(() => setPasswordMsg(""), 3000);
    },
  });

  const handleProfileSubmit = (e: FormEvent) => {
    e.preventDefault();
    updateProfileMutation.mutate();
  };

  const handlePasswordSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setPasswordMsg("❌ رمز جدید و تکرار آن مطابقت ندارند");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordMsg("❌ رمز جدید باید حداقل ۸ حرف باشد");
      return;
    }
    changePasswordMutation.mutate();
  };

  return (
    <AppLayout title="👤 پروفایل کاربری" subtitle="مشاهده و ویرایش اطلاعات شخصی">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* ── User Info Card ── */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-16 h-16 rounded-full bg-surface-700 flex items-center justify-center text-2xl">
              {profile?.username?.[0]?.toUpperCase() || "👤"}
            </div>
            <div>
              {isLoading ? (
                <Skeleton className="h-6 w-32 mb-1" />
              ) : (
                <h2 className="text-xl font-bold text-surface-100">{profile?.username}</h2>
              )}
              {profile?.roles?.[0] && (
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${ROLE_LABELS[profile.roles[0]]?.color || "bg-surface-600/20 text-surface-400"}`}>
                  {ROLE_LABELS[profile.roles[0]]?.label || profile.roles[0]}
                </span>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-surface-500">شناسه:</span>
              <span className="text-surface-300 mr-2 font-mono text-xs">{profile?.id || "—"}</span>
            </div>
            <div>
              <span className="text-surface-500">نام کاربری:</span>
              <span className="text-surface-300 mr-2">{profile?.username || "—"}</span>
            </div>
            <div>
              <span className="text-surface-500">ایمیل:</span>
              <span className="text-surface-300 mr-2">{profile?.email || "—"}</span>
            </div>
            <div>
              <span className="text-surface-500">تلفن:</span>
              <span className="text-surface-300 mr-2">{profile?.phone || "—"}</span>
            </div>
            <div>
              <span className="text-surface-500">وضعیت:</span>
              <span className={`mr-2 ${profile?.is_active ? "text-accent-emerald" : "text-accent-rose"}`}>
                {profile?.is_active ? "✅ فعال" : "❌ غیرفعال"}
              </span>
            </div>
            <div>
              <span className="text-surface-500">تایید شده:</span>
              <span className={`mr-2 ${profile?.is_verified ? "text-accent-emerald" : "text-surface-500"}`}>
                {profile?.is_verified ? "✅ بله" : "— خیر"}
              </span>
            </div>
            <div>
              <span className="text-surface-500">آخرین ورود:</span>
              <span className="text-surface-300 mr-2 text-xs">{formatDate(profile?.last_login || null)}</span>
            </div>
            <div>
              <span className="text-surface-500">تاریخ عضویت:</span>
              <span className="text-surface-300 mr-2 text-xs">{formatDate(profile?.created_at || null)}</span>
            </div>
          </div>
        </div>

        {/* ── Edit Profile Form ── */}
        <div className="glass-card p-6">
          <h3 className="text-lg font-bold text-surface-200 mb-4">✏️ ویرایش اطلاعات</h3>
          {profileMsg && (
            <div className={`px-4 py-2 rounded-lg mb-4 text-sm ${profileMsg.startsWith("✅") ? "bg-accent-emerald/10 text-accent-emerald" : "bg-accent-rose/10 text-accent-rose"}`}>
              {profileMsg}
            </div>
          )}
          <form onSubmit={handleProfileSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-surface-500 mb-1">نام و نام خانوادگی</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                placeholder="نام کامل"
              />
            </div>
            <div>
              <label className="block text-sm text-surface-500 mb-1">تلفن</label>
              <input
                type="text"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                placeholder="شماره تلفن"
              />
            </div>
            <div>
              <label className="block text-sm text-surface-500 mb-1">ایمیل</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                placeholder="example@email.com"
              />
            </div>
            <button
              type="submit"
              disabled={updateProfileMutation.isPending}
              className="w-full bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white rounded-lg py-2.5 font-medium transition"
            >
              {updateProfileMutation.isPending ? "در حال ذخیره..." : "ذخیره تغییرات"}
            </button>
          </form>
        </div>

        {/* ── Change Password Form ── */}
        <div className="glass-card p-6">
          <h3 className="text-lg font-bold text-surface-200 mb-4">🔒 تغییر رمز عبور</h3>
          {passwordMsg && (
            <div className={`px-4 py-2 rounded-lg mb-4 text-sm ${passwordMsg.startsWith("✅") ? "bg-accent-emerald/10 text-accent-emerald" : "bg-accent-rose/10 text-accent-rose"}`}>
              {passwordMsg}
            </div>
          )}
          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-surface-500 mb-1">رمز عبور فعلی</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                placeholder="رمز عبور فعلی"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-surface-500 mb-1">رمز عبور جدید</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                placeholder="حداقل ۸ حرف"
                required
                minLength={8}
              />
            </div>
            <div>
              <label className="block text-sm text-surface-500 mb-1">تکرار رمز عبور جدید</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                placeholder="تکرار رمز عبور جدید"
                required
                minLength={8}
              />
            </div>
            <button
              type="submit"
              disabled={changePasswordMutation.isPending}
              className="w-full bg-accent-rose/80 hover:bg-accent-rose disabled:opacity-50 text-white rounded-lg py-2.5 font-medium transition"
            >
              {changePasswordMutation.isPending ? "در حال تغییر..." : "تغییر رمز عبور"}
            </button>
          </form>
        </div>

        {/* ── Login History ── */}
        <LoginHistorySection />
      </div>
    </AppLayout>
  );
}

function LoginHistorySection() {
  const { data: historyData, isLoading } = useQuery<{
    items: LoginHistoryItem[];
    total: number;
  }>({
    queryKey: ["login-history"],
    queryFn: async () => {
      const res = await apiGet<{ success: boolean; data: { items: LoginHistoryItem[]; total: number } }>(
        "/auth/login-history?limit=20"
      );
      return res.data || { items: [], total: 0 };
    },
    staleTime: 60_000,
  });

  const items = historyData?.items || [];

  function parseUA(ua: string): string {
    if (!ua) return "—";
    // Simplified user agent parsing
    if (ua.includes("Chrome")) return "Chrome";
    if (ua.includes("Firefox")) return "Firefox";
    if (ua.includes("Safari") && !ua.includes("Chrome")) return "Safari";
    if (ua.includes("Edge")) return "Edge";
    if (ua.includes("curl")) return "cURL";
    return ua.substring(0, 40);
  }

  return (
    <div className="glass-card p-6">
      <h3 className="text-lg font-bold text-surface-200 mb-4">🕐 تاریخچه ورودها</h3>
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-surface-500 text-sm text-center py-4">
          سابقه ورودی ثبت نشده است.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-700 text-surface-500">
                <th className="text-right py-2 px-3">تاریخ و ساعت</th>
                <th className="text-right py-2 px-3">آدرس IP</th>
                <th className="text-right py-2 px-3">مرورگر</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => (
                <tr
                  key={idx}
                  className="border-b border-surface-800 hover:bg-surface-800/50 transition-colors"
                >
                  <td className="py-2.5 px-3 text-surface-300 text-xs">
                    {formatDate(item.created_at)}
                  </td>
                  <td className="py-2.5 px-3 text-surface-400 font-mono text-xs">
                    {item.ip_address || "—"}
                  </td>
                  <td className="py-2.5 px-3 text-surface-400 text-xs">
                    {parseUA(item.user_agent)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
