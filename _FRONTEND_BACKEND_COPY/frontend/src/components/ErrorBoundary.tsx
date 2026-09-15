"use client";

import { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
  /** Optional page/section name shown in the error message */
  pageTitle?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error(
      `[ErrorBoundary] ${this.props.pageTitle || "Page"} error:`,
      error,
      errorInfo.componentStack
    );
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar placeholder */}
          <aside className="w-56 shrink-0 bg-surface-900/80 border-l border-surface-800" />

          {/* Error content */}
          <main className="flex-1 flex items-center justify-center p-8">
            <div className="glass-card p-8 max-w-lg w-full text-center">
              <span className="material-icons text-6xl text-accent-rose mb-4">
                error_outline
              </span>

              <h2 className="text-xl font-bold text-surface-200 mb-2">
                خطا در بارگذاری صفحه
              </h2>

              {this.props.pageTitle && (
                <p className="text-sm text-surface-400 mb-1">
                  {this.props.pageTitle}
                </p>
              )}

              <p className="text-xs text-surface-500 mb-6 leading-relaxed">
                مشکلی در نمایش این بخش پیش آمده است. این خطا می‌تواند ناشی از
                قطع ارتباط با سرور، داده‌های نامعتبر یا باگ در کد باشد.
              </p>

              {this.state.error && (
                <details className="mb-6 text-left">
                  <summary className="text-xs text-surface-500 cursor-pointer hover:text-surface-400 mb-2">
                    جزئیات فنی
                  </summary>
                  <pre className="bg-surface-800/50 border border-surface-700 rounded-lg p-3 text-[10px] text-surface-500 overflow-x-auto max-h-32 text-left whitespace-pre-wrap">
                    {this.state.error.name}: {this.state.error.message}
                  </pre>
                </details>
              )}

              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={this.handleRetry}
                  className="flex items-center gap-2 px-5 py-2.5 bg-primary-600 hover:bg-primary-500 text-white rounded-xl text-sm font-medium transition-all"
                >
                  <span className="material-icons text-base">refresh</span>
                  تلاش مجدد
                </button>
                <button
                  onClick={() => (window.location.href = "/")}
                  className="flex items-center gap-2 px-5 py-2.5 bg-surface-800 hover:bg-surface-700 text-surface-300 rounded-xl text-sm font-medium transition-all border border-surface-700"
                >
                  <span className="material-icons text-base">home</span>
                  بازگشت به خانه
                </button>
              </div>
            </div>
          </main>
        </div>
      );
    }

    return this.props.children;
  }
}
