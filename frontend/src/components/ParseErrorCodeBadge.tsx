// Parser failures record a structured code inside the message:
// ``ParseError[unexpected_shape]: Candlestick: 'candles' must be a list …``.
// The code is the actionable part — the prose after it changes freely — so
// every dashboard that lists failed syncs renders it as its own badge.
export const PARSE_ERROR_CODE_RE = /ParseError\[([a-z0-9_]+)\]/i;

export function parseErrorCode(message?: string | null): string | null {
  if (!message) return null;
  const match = PARSE_ERROR_CODE_RE.exec(message);
  return match ? match[1] : null;
}

// Drop the "ParseError[code]: " prefix once the code is shown as a badge, so
// the message is not repeated in the failure detail.
export function stripParseErrorPrefix(message?: string | null): string {
  if (!message) return "";
  return message.replace(/^ParseError\[[a-z0-9_]+\]:\s*/i, "");
}

export default function ParseErrorCodeBadge({ message }: { message?: string | null }) {
  const code = parseErrorCode(message);
  if (!code) return null;
  return (
    <code
      dir="ltr"
      className="shrink-0 whitespace-nowrap px-1.5 py-0.5 rounded border border-accent-rose/30 bg-accent-rose/10 font-mono text-[9px] font-normal text-accent-rose"
    >
      {code}
    </code>
  );
}
