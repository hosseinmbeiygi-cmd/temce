import { forwardRef, type HTMLAttributes, type PropsWithChildren } from "react";

type SSRSafeProps = HTMLAttributes<HTMLDivElement> & PropsWithChildren;

/**
 * A `<div>` wrapper that automatically adds `suppressHydrationWarning`
 * to suppress React hydration mismatch warnings for dynamic content
 * that legitimately differs between server and client (e.g., mock data
 * populated via `useClientData` / `useEffect` after hydration).
 *
 * This is a drop-in replacement for `<div suppressHydrationWarning>`
 * that DRYs up the attribute across the codebase.
 *
 * @example
 * ```tsx
 * <SSRSafe className="sentiment-stats" style={{ marginTop: 8 }}>
 *   <div className="value">{data}%</div>
 * </SSRSafe>
 * ```
 */
const SSRSafe = forwardRef<HTMLDivElement, SSRSafeProps>(
  ({ children, ...props }, ref) => {
    return (
      <div ref={ref} {...props} suppressHydrationWarning>
        {children}
      </div>
    );
  },
);

SSRSafe.displayName = "SSRSafe";

export default SSRSafe;
