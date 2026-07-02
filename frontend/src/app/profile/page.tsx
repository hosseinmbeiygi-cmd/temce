"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import { apiGet, apiPut, getStoredAuth } from "@/lib/api";

interface UserProfile {
  id: string;
  username: string;
  email: string;
  full_name: string;
  phone: string;
  roles: string[];
  is_active: boolean;
  is_verified: boolean;
  last_login: string;
  created_at: string;
}

export default function ProfilePage() {
  const auth = getStoredAuth();
  const [formData, setFormData] = useState({ full_name: "", phone: "", email: "" });

  const { data: user, isLoading } = useQuery({
    queryKey: ["user-profile"],
    queryFn: () => apiGet<UserProfile>("/auth/me", auth?.token),
    enabled: !!auth,
  });

  const updateMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) => apiPut("/auth/profile", data, auth?.token),
    onSuccess: () => {
      toast.success("پروفایل با موفقیت به‌روزرسانی شد");
    },
    onError: (err: Error) => toast.error(err.message || "خطا در به‌روزرسانی پروفایل"),
  });

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate(formData);
  };

  if (!auth) return <div className="flex h-screen items-center justify-center text-white bg-[#0a0a14]">لطفا ابتدا وارد حساب خود شوید.</div>;

  return (
    <AppLayout title="پروفایل کاربر" subtitle="مدیریت اطلاعات شخصی و تنظیمات حساب">
        <div className="max-w-3xl mx-auto">
          {isLoading ? (
            <div className="space-y-4">
              <div className="h-64 bg-surface-800 animate-pulse rounded-2xl" />
              <div className="h-32 bg-surface-800 animate-pulse rounded-2xl" />
            </div>
          ) : user ? (
            <div className="space-y-6">
              <div className="glass-card p-6 flex items-center gap-6">
                <div className="w-24 h-24 rounded-full bg-primary-600 flex items-center justify-center text-3xl font-bold text-white">
                  {user.username[0].toUpperCase()}
                </div>
                <div>
                  <h2 className="text-xl font-bold text-surface-100">{user.full_name || user.username}</h2>
                  <p className="text-sm text-surface-400">{user.email}</p>
                  <div className="flex gap-2 mt-2">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-surface-800 text-surface-400">{user.roles.join(", ")}</span>
                    {user.is_verified && <span className="text-xs px-2 py-0.5 rounded-full bg-accent-emerald/15 text-accent-emerald">تایید شده</span>}
                  </div>
                </div>
              </div>

              <form onSubmit={handleSave} className="glass-card p-6 space-y-4">
                <h3 className="font-bold text-surface-200 mb-4">ویرایش اطلاعات</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-surface-500 mb-1">نام کامل</label>
                    <input 
                      type="text" 
                      value={formData.full_name} 
                      onChange={(e) => setFormData({...formData, full_name: e.target.value})}
                      className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500" 
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-surface-500 mb-1">تلفن</label>
                    <input 
                      type="text" 
                      value={formData.phone} 
                      onChange={(e) => setFormData({...formData, phone: e.target.value})}
                      className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500" 
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs text-surface-500 mb-1">ایمیل</label>
                    <input 
                      type="email" 
                      value={formData.email} 
                      onChange={(e) => setFormData({...formData, email: e.target.value})}
                      className="w-full px-3 py-2 bg-surface-800 border border-surface-700 rounded text-surface-200 text-sm focus:outline-none focus:border-primary-500" 
                    />
                  </div>
                </div>
                <button 
                  type="submit" 
                  disabled={updateMutation.isPending}
                  className="px-6 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded text-sm font-medium transition disabled:opacity-50"
                >
                  {updateMutation.isPending ? "در حال ذخیره..." : "ذخیره تغییرات"}
                </button>
              </form>
            </div>
          ) : (
            <div className="text-center py-12 text-surface-500">اطلاعات کاربر یافت نشد.</div>
          )}
        </div>
    </AppLayout>
  );
}
