export const debug = {
  log: (message: string, data?: unknown) => {
    console.log(`🔍 [DEBUG] ${message}`, data || "");
  },
  warn: (message: string, data?: unknown) => {
    console.warn(`⚠️ [DEBUG] ${message}`, data || "");
  },
  error: (message: string, error?: unknown) => {
    console.error(`❌ [DEBUG] ${message}`, error || "");
  },
  table: (data: unknown) => {
    console.table(data);
  },
  group: (name: string, fn: () => void) => {
    console.group(`🔍 ${name}`);
    fn();
    console.groupEnd();
  },
};

export function inspectData(data: unknown, label: string = "Data") {
  debug.group(label, () => {
    debug.log("Type:", typeof data);
    debug.log("Is Array:", Array.isArray(data));
    debug.log("Is Object:", data && typeof data === "object" && !Array.isArray(data));
    debug.log("Keys:", data && typeof data === "object" ? Object.keys(data) : "N/A");
    debug.log("Length:", data && typeof data === "object" && "length" in data ? (data as { length: number }).length : "N/A");
    debug.table(data);
  });
}

export function safeExtractArray(response: unknown, endpoint: string = "unknown"): unknown[] {
  debug.log(`📡 Extracting array from ${endpoint}`, response);

  if (Array.isArray(response)) {
    debug.log(`✅ ${endpoint}: Direct array, length: ${response.length}`);
    return response;
  }

  if (response && typeof response === "object") {
    const obj = response as Record<string, unknown>;
    const keys = ["data", "items", "results", "list", "records", "content", "docs"] as const;
    for (const key of keys) {
      if (Array.isArray(obj[key])) {
        debug.log(`✅ ${endpoint}: Extracted from "${key}", length: ${(obj[key] as unknown[]).length}`);
        return obj[key] as unknown[];
      }
    }
    const values = Object.values(obj);
    if (values.length > 0) {
      debug.log(`⚠️ ${endpoint}: Using Object.values(), length: ${values.length}`);
      return values;
    }
  }

  debug.error(`❌ ${endpoint}: No array found!`);
  return [];
}