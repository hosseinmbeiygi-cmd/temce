"use client";

/**
 * Audit badge — shows audited (green) or unaudited (amber) status
 * for Codal announcements, detected from the announcement title.
 */
export function AuditBadge({ status }: { status: string }) {
  if (!status) return null;

  const isAudited = status === "audited";
  return (
    <span
      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
        isAudited
          ? "bg-accent-emerald/15 text-accent-emerald"
          : "bg-accent-amber/15 text-accent-amber"
      }`}
      title={isAudited ? "حسابرسی شده" : "حسابرسی نشده"}
    >
      {isAudited ? "✓ حسابرسی شده" : "! حسابرسی نشده"}
    </span>
  );
}
