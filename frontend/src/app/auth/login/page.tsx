"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import { apiPost, storeAuth } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await apiPost<{ user: Record<string, unknown>; access_token: string; refresh_token: string }>("/auth/login", {
        username,
        password,
      });
      storeAuth(data);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-surface-950 text-white font-sans" dir="rtl">
      <Sidebar />
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="glass-card p-8">
            <h1 className="text-2xl font-bold mb-6 text-center gradient-text">ورود به سامانه</h1>
            {error && (
              <div className="bg-rose-500/10 border border-rose-500/30 text-rose-400 px-4 py-2 rounded-lg mb-4 text-sm">
                {error}
              </div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">نام کاربری</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                  placeholder="نام کاربری خود را وارد کنید"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">رمز عبور</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                  placeholder="رمز عبور خود را وارد کنید"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white rounded-lg py-2.5 font-medium transition"
              >
                {loading ? "در حال ورود..." : "ورود"}
              </button>
            </form>
            <p className="text-center text-sm text-gray-500 mt-6">
              حساب کاربری ندارید؟{" "}
              <Link href="/auth/register" className="text-primary-400 hover:text-primary-300">
                ثبت‌نام کنید
              </Link>
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
