"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import AppLayout from "@/components/layout/AppLayout";
import Skeleton from "@/components/Skeleton";
import { apiGet, apiPut } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  roles: string[];
  is_active: boolean;
  is_verified: boolean;
  last_login: string | null;
  created_at: string | null;
}

interface UsersResponse {
  items: User[];
  total: number;
  page: number;
  page_size: number;
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
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

export default function AdminUsersPage() {
  const queryClient = useQueryClient();
  const { user: currentUser } = useAuth();
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery<UsersResponse>({
    queryKey: ["admin-users", page],
    queryFn: async () => {
      const res = await apiGet<UsersResponse>(`/auth/users?page=${page}&page_size=20`);
      return res;
    },
    staleTime: 30_000,
  });

  const toggleStatusMutation = useMutation({
    mutationFn: async (userId: string) => {
      return apiPut<{ success: boolean; data: { id: string; is_active: boolean } }>(
        `/auth/users/${userId}/toggle-status`
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const changeRoleMutation = useMutation({
    mutationFn: async ({ userId, role }: { userId: string; role: string }) => {
      return apiPut<{ success: boolean; data: { id: string; new_role: string } }>(
        `/auth/users/${userId}/role?role=${role}`
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
    },
  });

  const users = data?.items || [];
  const total = data?.total || 0;

  return (
    <AppLayout title="👥 مدیریت کاربران" subtitle="تغییر نقش، فعال/غیرفعال کردن حساب‌ها">
      <div className="glass-card p-4 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-surface-400">
              تعداد کل: <span className="text-surface-200 font-bold">{total}</span> کاربر
            </p>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : users.length === 0 ? (
        <div className="glass-card p-8 text-center text-surface-500">
          <p className="text-3xl mb-2">👤</p>
          <p>هیچ کاربری یافت نشد</p>
        </div>
      ) : (
        <div className="space-y-3">
          {users.map((u) => {
            const isCurrentUser = u.id === currentUser?.id;
            const roleInfo = ROLE_LABELS[u.roles[0]] || ROLE_LABELS.viewer;

            return (
              <div
                key={u.id}
                className={`glass-card p-4 transition-all ${isCurrentUser ? "ring-1 ring-primary-500/30" : ""}`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-surface-700 flex items-center justify-center text-lg shrink-0">
                      {u.username[0]?.toUpperCase() || "👤"}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-surface-100 text-sm">{u.username}</span>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${roleInfo.color}`}>
                          {roleInfo.label}
                        </span>
                        {!u.is_active && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-surface-700 text-surface-400">
                            غیرفعال
                          </span>
                        )}
                        {isCurrentUser && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary-500/20 text-primary-400">
                            شما
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-[11px] text-surface-500">
                        <span>{u.email}</span>
                        {u.full_name && <span>· {u.full_name}</span>}
                        <span>· آخرین ورود: {formatDate(u.last_login)}</span>
                      </div>
                    </div>
                  </div>

                  {!isCurrentUser && (
                    <div className="flex items-center gap-2 shrink-0">
                      {/* Role Selector */}
                      <select
                        value={u.roles[0] || "viewer"}
                        onChange={(e) =>
                          changeRoleMutation.mutate({ userId: u.id, role: e.target.value })
                        }
                        disabled={changeRoleMutation.isPending}
                        className="bg-surface-800 border border-surface-700 rounded-lg px-3 py-1.5 text-xs text-surface-200 focus:outline-none focus:border-primary-500 transition disabled:opacity-50"
                      >
                        <option value="admin">ادمین</option>
                        <option value="analyst">تحلیلگر</option>
                        <option value="user">کاربر</option>
                        <option value="viewer">بیننده</option>
                      </select>

                      {/* Toggle Status */}
                      <button
                        onClick={() => toggleStatusMutation.mutate(u.id)}
                        disabled={toggleStatusMutation.isPending}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition disabled:opacity-50 ${
                          u.is_active
                            ? "bg-accent-rose/10 text-accent-rose hover:bg-accent-rose/20"
                            : "bg-accent-emerald/10 text-accent-emerald hover:bg-accent-emerald/20"
                        }`}
                      >
                        {u.is_active ? "غیرفعال" : "فعال"}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {total > 20 && (
        <div className="flex items-center justify-center gap-2 mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-300 hover:bg-surface-700 transition disabled:opacity-30"
          >
            قبلی
          </button>
          <span className="text-xs text-surface-500">
            صفحه {page} از {Math.ceil(total / 20)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page * 20 >= total}
            className="px-3 py-1.5 rounded-lg text-xs bg-surface-800 text-surface-300 hover:bg-surface-700 transition disabled:opacity-30"
          >
            بعدی
          </button>
        </div>
      )}
    </AppLayout>
  );
}
