"use client";

import { useState } from "react";
import Sidebar from "@/components/Sidebar";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface TestItem {
  name: string;
  status: "passed" | "failed" | "skipped" | "error";
  duration: number;
  message: string;
}

interface TestRunData {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  errors: number;
  duration: number;
  results: TestItem[];
}

export default function TestsPage() {
  const [data, setData] = useState<TestRunData | null>(null);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string>("all");

  async function handleRun() {
    setLoading(true);
    setData(null);
    try {
      const res = await fetch(`${API}/tests/run`, { method: "POST" });
      const json = await res.json();
      if (json.success) setData(json.data);
    } catch {
      /* ignore */
    }
    setLoading(false);
  }

  const filtered =
    data?.results.filter((t) => filter === "all" || t.status === filter) ?? [];

  const count = (status: string) =>
    data?.results.filter((t) => t.status === status).length ?? 0;

  return (
    <div className="min-h-screen flex bg-gray-50 font-sans" dir="rtl">
      <Sidebar />
      <main className="flex-1 p-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-800">اجرای تست‌ها</h1>
          <button
            onClick={handleRun}
            disabled={loading}
            className="bg-blue-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "در حال اجرا..." : "اجرای همه تست‌ها"}
          </button>
        </div>

        {data && (
          <div className="grid grid-cols-4 gap-4 mb-6">
            {[
              { label: "کل", value: data.total, color: "bg-gray-500" },
              { label: "موفق", value: data.passed, color: "bg-green-500" },
              { label: "ناموفق", value: data.failed, color: "bg-red-500" },
              { label: "خطا", value: data.errors, color: "bg-orange-500" },
            ].map((item) => (
              <div key={item.label} className="bg-white rounded-xl shadow-sm p-4 border border-gray-100 text-center">
                <p className={`text-3xl font-bold ${item.color.replace("bg-", "text-")}-600`}>{item.value}</p>
                <p className="text-sm text-gray-500 mt-1">{item.label}</p>
              </div>
            ))}
          </div>
        )}

        {data && (
          <div className="text-sm text-gray-500 mb-4">
            زمان اجرا: {data.duration} ثانیه | {data.total} تست
          </div>
        )}

        {data && (
          <div className="flex gap-2 mb-4">
            {["all", "passed", "failed", "skipped", "error"].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 text-sm rounded-lg border ${filter === f ? "bg-blue-600 text-white border-blue-600" : "bg-white text-gray-600 border-gray-300"}`}
              >
                {f === "all" ? "همه" : f === "passed" ? "موفق" : f === "failed" ? "ناموفق" : f === "skipped" ? "نادیده" : "خطا"} ({f === "all" ? data.total : count(f)})
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-3" />
            <p className="text-gray-500">در حال اجرای تست‌ها...</p>
          </div>
        )}

        {filtered.length > 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-100 text-gray-600">
                    <th className="p-3 text-right">نام تست</th>
                    <th className="p-3 text-center">نتیجه</th>
                    <th className="p-3 text-center">زمان (ثانیه)</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((t, i) => (
                    <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="p-3 text-gray-700 max-w-md truncate" title={t.name}>
                        {t.name}
                      </td>
                      <td className="p-3 text-center">
                        <span
                          className={`inline-block px-2 py-0.5 text-xs rounded-full font-medium ${
                            t.status === "passed"
                              ? "bg-green-100 text-green-700"
                              : t.status === "failed"
                                ? "bg-red-100 text-red-700"
                                : t.status === "skipped"
                                  ? "bg-yellow-100 text-yellow-700"
                                  : "bg-orange-100 text-orange-700"
                          }`}
                        >
                          {t.status === "passed" ? "موفق" : t.status === "failed" ? "ناموفق" : t.status === "skipped" ? "نادیده" : "خطا"}
                        </span>
                      </td>
                      <td className="p-3 text-center text-gray-500">{t.duration.toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {!data && !loading && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg mb-2">هنوز تستی اجرا نشده</p>
            <p className="text-sm">روی دکمه "اجرای همه تست‌ها" کلیک کنید</p>
          </div>
        )}
      </main>
    </div>
  );
}
