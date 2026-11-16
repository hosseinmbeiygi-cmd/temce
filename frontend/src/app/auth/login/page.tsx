"use client";

import { Suspense, useState, FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/";
  const sessionExpired = searchParams.get("reason") === "session_expired";
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      router.push(redirectTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-md">
      <div className="glass-card p-8">
        <h1 className="text-2xl font-bold mb-6 text-center gradient-text">ورود به سامانه</h1>
        {sessionExpired && !error && (
          <div
            role="status"
            className="bg-amber-500/10 border border-amber-500/30 text-amber-300 px-4 py-2 rounded-lg mb-4 text-sm"
          >
            نشست شما منقضی شده است — لطفاً دوباره وارد شوید.
          </div>
        )}
        {error && (
          <div role="alert" className="bg-rose-500/10 border border-rose-500/30 text-rose-400 px-4 py-2 rounded-lg mb-4 text-sm">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-username" className="block text-sm text-ink-2 mb-1">نام کاربری</label>
            <input
              id="login-username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-soft border border-line rounded-lg px-4 py-2.5 text-ink placeholder:text-ink-3 focus:outline-none focus:border-primary-500 transition"
              placeholder="نام کاربری خود را وارد کنید"
              required
            />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-sm text-ink-2 mb-1">رمز عبور</label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-soft border border-line rounded-lg px-4 py-2.5 text-ink placeholder:text-ink-3 focus:outline-none focus:border-primary-500 transition"
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
        <div className="mt-5">
          <div className="relative flex items-center gap-3 text-ink-3 text-xs before:flex-1 before:h-px before:bg-line after:flex-1 after:h-px after:bg-line">
            یا
          </div>
          <a
            href="/api/v1/auth/google/redirect"
            className="mt-3 w-full flex items-center justify-center gap-2.5 bg-soft hover:bg-elevated border border-line rounded-lg px-4 py-2.5 text-ink text-sm font-medium transition"
          >
            <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            ورود با Google
          </a>
        </div>
        <p className="text-center text-sm text-ink-3 mt-6">
          حساب کاربری ندارید؟{" "}
          <Link href="/auth/register" className="text-primary-500 hover:text-primary-400">
            ثبت‌نام کنید
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-canvas text-ink font-sans flex items-center justify-center p-6" dir="rtl">
      <Suspense fallback={
        <div className="w-full max-w-md">
          <div className="glass-card p-8 text-center text-ink-3">
            <p className="text-3xl mb-2">⏳</p>
            <p>در حال بارگذاری...</p>
          </div>
        </div>
      }>
        <LoginForm />
      </Suspense>
    </div>
  );
}
