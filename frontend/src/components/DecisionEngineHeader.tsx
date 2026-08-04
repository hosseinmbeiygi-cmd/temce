"use client";

// ── Types ───────────────────────────────────────────────────────────

export interface TabItem {
  key: string;
  label: string;
  icon: string;
}

export interface PrincipleItem {
  code: string;
  name: string;
  description: string;
}

export interface DataSourceItem {
  code: string;
  name: string;
  description: string;
}

export interface DecisionEngineHeaderProps {
  /** نام سامانه (مثلاً "سامانه تصمیم‌یار بورس تهران") */
  title: string;
  /** توضیح کوتاه زیر عنوان */
  description?: string;
  /** نسخه (مثلاً "Enterprise-Final-1.0") */
  version?: string;
  /** نوع سامانه (مثلاً "Multi-Layer Decision Support System") */
  type?: string;
  /** اصول معماری */
  principles?: PrincipleItem[];
  /** منابع داده */
  dataSources?: DataSourceItem[];
  /** تب‌های ناوبری */
  tabs: TabItem[];
  /** تب فعال */
  activeTab: string;
  /** رویداد تغییر تب */
  onTabChange: (key: string) => void;
}

// ── Component ───────────────────────────────────────────────────────

export default function DecisionEngineHeader({
  title,
  description,
  version,
  type,
  principles,
  dataSources,
  tabs,
  activeTab,
  onTabChange,
}: DecisionEngineHeaderProps) {
  return (
    <>
      {/* ── System Header Card ── */}
      <div className="glass-card p-5 mb-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-black text-surface-100 mb-1">{title}</h1>
            {description && (
              <p className="text-xs text-surface-400 max-w-2xl leading-relaxed">{description}</p>
            )}
          </div>
          {(version || type) && (
            <div className="text-right shrink-0">
              {version && (
                <div className="text-[9px] text-surface-500 bg-surface-800 px-2 py-1 rounded-lg">
                  نسخه {version}
                </div>
              )}
              {type && (
                <div className="text-[9px] text-surface-500 mt-1">{type}</div>
              )}
            </div>
          )}
        </div>

        {/* Principles */}
        {principles && principles.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-surface-800/50">
            {principles.map((p) => (
              <span
                key={p.code}
                className="text-[9px] px-2 py-1 bg-surface-800/50 rounded-full text-surface-400 border border-surface-700/30"
                title={p.description}
              >
                <span className="font-bold text-primary-400">{p.code}</span>{" "}
                {p.name}
              </span>
            ))}
          </div>
        )}

        {/* Data Sources */}
        {dataSources && dataSources.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {dataSources.map((ds) => (
              <span
                key={ds.code}
                className="text-[9px] px-2 py-1 bg-accent-cyan/5 border border-accent-cyan/10 rounded-full text-accent-300"
                title={ds.description}
              >
                {ds.name}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Tab Navigation ── */}
      <div className="flex items-center gap-1 mb-4 overflow-x-auto pb-1">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onTabChange(tab.key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-medium transition-all shrink-0 ${
              activeTab === tab.key
                ? "bg-primary-600 text-white shadow-lg shadow-primary-600/20"
                : "bg-surface-800 text-surface-400 hover:text-surface-200"
            }`}
          >
            <span className="material-icons text-sm">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>
    </>
  );
}
