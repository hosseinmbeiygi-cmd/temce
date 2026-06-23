"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import { Card } from "@/components/ui/Card";
import Skeleton from "@/components/Skeleton";
import { apiPost } from "@/lib/api";

const MODELS = [
  { id: "linear_regression", name: "رگرسیون خطی", type: "shallow", description: "مدل رگرسیون خطی ساده برای پیش‌بینی قیمت" },
  { id: "random_forest", name: "جنگل تصادفی", type: "shallow", description: "مدل جنگل تصادفی برای پیش‌بینی روند بازار" },
  { id: "xgboost", name: "XGBoost", type: "shallow", description: "مدل گرادیان بوستینگ برای پیش‌بینی دقیق" },
  { id: "logistic_regression", name: "رگرسیون لجستیک", type: "shallow", description: "مدل طبقه‌بندی برای سیگنال‌های خرید/فروش" },
];

const SYMBOLS = ["فولاد", "شپنا", "وبملت", "خودرو", "فملی"];

const EXAMPLE_FEATURES: Record<string, Record<string, number>> = {
  فولاد: { price_close: 38500, volume: 2500000, rsi_14: 58.5, macd: 120.5, sma_20: 37200, sma_50: 35800, volatility: 0.015 },
  شپنا: { price_close: 45200, volume: 1800000, rsi_14: 62.1, macd: 95.3, sma_20: 43800, sma_50: 42100, volatility: 0.012 },
  وبملت: { price_close: 14200, volume: 3200000, rsi_14: 45.2, macd: -28.7, sma_20: 14800, sma_50: 15200, volatility: 0.018 },
};

export default function ExperimentsPage() {
  const [selectedModel, setSelectedModel] = useState(MODELS[0].id);
  const [selectedSymbol, setSelectedSymbol] = useState("فولاد");

  const predictMutation = useMutation({
    mutationFn: async () => {
      const features = EXAMPLE_FEATURES[selectedSymbol] || EXAMPLE_FEATURES.فولاد;
      return await apiPost<any>(`/ml/predict/${selectedModel}`, features);
    },
  });

  const trainMutation = useMutation({
    mutationFn: async () => {
      return await apiPost<any>('/ml/train', {
        model_id: selectedModel,
        symbol: selectedSymbol,
        start_date: "1403-01-01",
        end_date: "1403-06-30",
      });
    },
    onSuccess: () => toast.success("مدل با موفقیت آموزش دید"),
    onError: (err: any) => toast.error(err.message),
  });

  return (
    <AppLayout title="آزمایش‌های یادگیری ماشین">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <Card title="مدل‌های موجود">
            <div className="space-y-2">
              {MODELS.map(m => (
                <button key={m.id} onClick={() => setSelectedModel(m.id)}
                  className={`w-full text-right p-3 rounded-lg border text-sm transition-all ${selectedModel === m.id ? "bg-blue-50 border-blue-500" : "bg-gray-50 border-gray-200 hover:bg-gray-100"}`}>
                  <p className="font-medium text-gray-700">{m.name}</p>
                  <p className="text-xs text-gray-400">{m.description}</p>
                </button>
              ))}
            </div>
          </Card>

          <Card title="آموزش مدل">
            <label className="block mb-2 text-sm text-gray-600">نماد</label>
            <select className="w-full border rounded-lg px-3 py-2 mb-3 text-sm" value={selectedSymbol} onChange={e => setSelectedSymbol(e.target.value)}>
              {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button onClick={() => trainMutation.mutate()} disabled={trainMutation.isPending}
              className="w-full bg-green-600 text-white py-2.5 rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors">
              {trainMutation.isPending ? "در حال آموزش..." : "آموزش مدل"}
            </button>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <Card title="پیش‌بینی با مدل">
            <div className="flex items-center gap-3 mb-4">
              <label className="text-sm text-gray-600">نماد:</label>
              <select className="border rounded-lg px-3 py-2 text-sm" value={selectedSymbol} onChange={e => setSelectedSymbol(e.target.value)}>
                {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <button onClick={() => predictMutation.mutate()} disabled={predictMutation.isPending}
                className="bg-blue-600 text-white px-5 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {predictMutation.isPending ? "..." : "پیش‌بینی"}
              </button>
            </div>

            {predictMutation.isPending ? (
              <Skeleton className="h-40 w-full rounded-xl" />
            ) : predictMutation.data ? (
              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
                <h3 className="text-sm font-semibold text-gray-600 mb-4">نتیجه پیش‌بینی</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <p className="text-xs text-gray-500 mb-1">قیمت پیش‌بینی شده</p>
                    <p className="text-3xl font-bold text-blue-600">{(predictMutation.data as any).prediction?.toLocaleString() || "—"}</p>
                    <p className="text-xs text-gray-400 mt-1">ریال</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xs text-gray-500 mb-1">اطمینان</p>
                    <p className="text-3xl font-bold text-green-600">{((predictMutation.data as any).confidence * 100).toFixed(0)}%</p>
                    <div className="w-full bg-gray-200 rounded-full h-2.5 mt-2">
                      <div className="bg-green-500 h-2.5 rounded-full transition-all" style={{ width: `${(predictMutation.data as any).confidence * 100}%` }} />
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400 border-2 border-dashed border-gray-200 rounded-xl">
                برای دریافت پیش‌بینی، روی دکمه "پیش‌بینی" کلیک کنید.
              </div>
            )}
          </Card>
        </div>
      </div>
    </AppLayout>
  );
}
