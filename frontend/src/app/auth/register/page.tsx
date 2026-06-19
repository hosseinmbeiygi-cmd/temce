"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import { apiPost, storeAuth } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await apiPost<{ user: any; access_token: string; refresh_token: string }>("/auth/register", {
        username,
        email,
        password,
        full_name: fullName,
      });
      storeAuth(data);
      router.push("/");
    } catch (err: any) {
      setError(err.message || "Registration failed");
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
            <h1 className="text-2xl font-bold mb-6 text-center gradient-text">ثبت‌نام در سامانه</h1>
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
                  placeholder="حداقل ۳ حرف (لاتین)"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">ایمیل</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                  placeholder="example@email.com"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">نام و نام خانوادگی</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                  placeholder="اختیاری"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">رمز عبور</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary-500 transition"
                  placeholder="حداقل ۸ حرف"
                  required
                  minLength={8}
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-primary-600 hover:bg-primary-500 disabled:opacity-50 text-white rounded-lg py-2.5 font-medium transition"
              >
                {loading ? "در حال ثبت‌نام..." : "ثبت‌نام"}
              </button>
            </form>
            <p className="text-center text-sm text-gray-500 mt-6">
              قبلاً ثبت‌نام کرده‌اید؟{" "}
              <Link href="/auth/login" className="text-primary-400 hover:text-primary-300">
                وارد شوید
              </Link>
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
