"use client";

import { type ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";

// ── RoleGate: renders children only if user has the required role ──

interface RoleGateProps {
  /** Minimum role required to see the children (role hierarchy: admin > analyst > user > viewer) */
  role?: string;
  /** Any of these roles will allow access (OR logic) */
  anyOf?: string[];
  /** Children to render if access is granted */
  children: ReactNode;
  /** Fallback to render if access is denied (default: render nothing) */
  fallback?: ReactNode;
}

/**
 * RoleGate — conditionally renders children based on user role.
 *
 * Role hierarchy: admin > analyst > user > viewer
 * - Admin always has access to everything
 * - "analyst" role includes "user" and "viewer" permissions
 *
 * Usage:
 *   <RoleGate role="admin"><DeleteButton /></RoleGate>
 *   <RoleGate anyOf={["analyst", "admin"]}><ExportButton /></RoleGate>
 *   <RoleGate role="user" fallback={<p>ورود کنید</p>}>...</RoleGate>
 */
export function RoleGate({ role, anyOf, children, fallback = null }: RoleGateProps) {
  const { hasRole, hasAnyRole, isLoading, isAuthenticated } = useAuth();

  // Don't flash content while auth is loading
  if (isLoading) return null;

  // Not authenticated — deny access
  if (!isAuthenticated) return <>{fallback}</>;

  // Check access
  let allowed = false;
  if (anyOf && anyOf.length > 0) {
    allowed = hasAnyRole(...anyOf);
  } else if (role) {
    allowed = hasRole(role);
  } else {
    // No role requirement — any authenticated user can see
    allowed = true;
  }

  return allowed ? <>{children}</> : <>{fallback}</>;
}

// ── RoleBadge: shows the user's current role as a badge ──

const ROLE_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  admin: { bg: "bg-rose-500/20", text: "text-rose-400", label: "ادمین" },
  analyst: { bg: "bg-amber-500/20", text: "text-amber-400", label: "تحلیلگر" },
  user: { bg: "bg-emerald-500/20", text: "text-emerald-400", label: "کاربر" },
  viewer: { bg: "bg-surface-600/20", text: "text-surface-400", label: "بیننده" },
};

export function RoleBadge() {
  const { user, isAuthenticated } = useAuth();
  if (!isAuthenticated || !user?.roles?.length) return null;

  const topRole = user.roles[0] ?? "viewer";
  const colors = ROLE_COLORS[topRole] ?? ROLE_COLORS.viewer;

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text}`}>
      {colors.label}
    </span>
  );
}
