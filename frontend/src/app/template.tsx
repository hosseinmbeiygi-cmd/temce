/**
 * Route transition — App Router remounts <template> on every navigation, so a
 * plain CSS animation replays on each page change. Deliberately CSS-only (no
 * framer-motion here): zero JS, zero hydration cost per navigation, and the
 * global prefers-reduced-motion rule neutralizes it automatically.
 */
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="page-enter">{children}</div>;
}
