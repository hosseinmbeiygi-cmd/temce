// ── Client-Only Wrapper ─────────────────────
// Wraps children with next/dynamic (ssr: false) so Recharts
// only renders in the browser, eliminating SSR dimension warnings.

import dynamic from "next/dynamic";
import { type ReactNode } from "react";

function ClientOnlyInner({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

const ClientOnly = dynamic(() => Promise.resolve({ default: ClientOnlyInner }), {
  ssr: false,
});

export default ClientOnly;
