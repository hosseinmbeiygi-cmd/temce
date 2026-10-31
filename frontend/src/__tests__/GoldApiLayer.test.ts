// F2 + F4 — لایهٔ API مشترک gold (قراردادهای C3، C4، C5).
//
// دو واقعیت هم‌زمان پوشش داده می‌شوند تا merge سه‌طرفه امن باشد:
//   * امروز: /snapshot در خطا HTTP 200 با {"success": false, "data": null,
//     "error": {"message": <متن داخلی>}} می‌دهد و /dca/planبدون پاکت پاسخ
//     می‌دهد (api.py:95-103 و :199).
//   / فردا (C3/C5): HTTP 503 با {"success": false, "error":
//     "snapshot_unavailable"} و پاکت {"success": true, "data": …}.
// فرانت باید هر دو را بپذیرد، هیچ‌وقت undefined به React Query ندهد، و متن
// خطای داخلی را به UI نرساند.

import { beforeEach, describe, expect, it, vi } from "vitest";

const REFRESH_TOKEN = "fake-test-access-token";

/** پاسخ‌های/scripted را به ازای مسیر برمی‌گرداند. */
function installFetch(handler: (url: string) => { status: number; body: unknown }) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetchMock = vi.fn(async (input: string, init?: RequestInit): Promise<Response> => {
    calls.push({ url: input, init });
    if (input.endsWith("/auth/refresh")) {
      return {
        ok: true,
        status: 200,
        json: async (): Promise<unknown> => ({ success: true, data: { access_token: REFRESH_TOKEN } }),
        text: async (): Promise<string> => "",
      } as unknown as Response;
    }
    const { status, body } = handler(input);
    const text = JSON.stringify(body);
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async (): Promise<unknown> => JSON.parse(text),
      text: async (): Promise<string> => text,
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

const HEALTHY_SNAPSHOT = {
  snapshot_at: "2026-10-24T10:00:00Z",
  references: {
    xau_usd: 2345.67,
    usd_irt: 900000,
    aed_irt: 245000,
    aed_parity_usd: 3.6725,
    aed_gap_pct: 1.25,
    source: "brsapi",
    age_seconds: 12,
  },
  gold: {},
  coins: {},
  funds: [],
  score: {
    total: 40,
    decision: "YELLOW",
    components: {},
    hard_stop_active: false,
    hard_stop_reason: null,
  },
  quality_flag: "clean",
};

const BARE_DCA_PLAN = {
  total_capital_irt: 100000000,
  ladder: [],
  recommended_vehicle: "etf",
  total_fee_irt: 120000,
  net_investable_irt: 99880000,
  stop_loss_pct: 8,
  take_profit_pct: 25,
};

describe("gold API layer (F2/F4 — C3, C4, C5)", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("getSnapshot returns the data on a healthy envelope", async () => {
    installFetch(() => ({ status: 200, body: { success: true, data: HEALTHY_SNAPSHOT } }));
    const { getSnapshot } = await import("@/lib/goldApi");
    await expect(getSnapshot()).resolves.toMatchObject({ snapshot_at: HEALTHY_SNAPSHOT.snapshot_at });
  });

  it("getSnapshot rejects (never resolves undefined) when the backend answers 200 with success:false", async () => {
    installFetch(() => ({
      status: 200,
      body: { success: false, data: null, error: { message: "Traceback: division by zero in bubbler.py" } },
    }));
    const { getSnapshot, GoldAPIError, isServiceUnavailable } = await import("@/lib/goldApi");
    const err = await getSnapshot().catch((e) => e);
    expect(err).toBeInstanceOf(GoldAPIError);
    // تعریف‌نشده بودنِ r.data باگ اصلی بود: هیچ‌وقت undefined نده
    expect(err).not.toBeUndefined();
    expect(isServiceUnavailable(err)).toBe(true);
    // C3: متن خطای داخلی نباید به UI برسد
    expect(err.message).not.toMatch(/Traceback|bubbler/);
  });

  it("getSnapshot maps the C3 503 body to an explicit unavailable error", async () => {
    installFetch(() => ({ status: 503, body: { success: false, error: "snapshot_unavailable" } }));
    const { getSnapshot, GoldAPIError, isServiceUnavailable, SNAPSHOT_UNAVAILABLE } =
      await import("@/lib/goldApi");
    const err = await getSnapshot().catch((e) => e);
    expect(err).toBeInstanceOf(GoldAPIError);
    expect(err.status).toBe(503);
    expect(err.code).toBe(SNAPSHOT_UNAVAILABLE);
    expect(isServiceUnavailable(err)).toBe(true);
  });

  it("still distinguishes a non-outage failure from an outage", async () => {
    installFetch(() => ({ status: 500, body: { detail: "boom" } }));
    const { getSnapshot, isServiceUnavailable } = await import("@/lib/goldApi");
    const err = await getSnapshot().catch((e) => e);
    expect(isServiceUnavailable(err)).toBe(false);
  });

  it("planDCA accepts both the bare payload of today and the C5 {success,data} envelope", async () => {
    // امروز: response_model=DCAResponse → بدون پاکت
    const bare = installFetch(() => ({ status: 200, body: BARE_DCA_PLAN }));
    vi.resetModules();
    let mod = await import("@/lib/goldApi");
    await expect(
      mod.planDCA({ total_capital_irt: 100000000, risk_profile: "balanced" }),
    ).resolves.toMatchObject({ recommended_vehicle: "etf" });

    // C5: پاکت‌دار
    vi.unstubAllGlobals();
    installFetch(() => ({ status: 200, body: { success: true, data: BARE_DCA_PLAN } }));
    vi.resetModules();
    mod = await import("@/lib/goldApi");
    await expect(
      mod.planDCA({ total_capital_irt: 100000000, risk_profile: "aggressive" }),
    ).resolves.toMatchObject({ net_investable_irt: 99880000 });
    expect(bare.calls.length).toBeGreaterThan(0);
  });

  it("planDCA does not send current_score any more (C4)", async () => {
    const { calls } = installFetch(() => ({ status: 200, body: BARE_DCA_PLAN }));
    const { planDCA } = await import("@/lib/goldApi");
    await planDCA({ total_capital_irt: 50000000, risk_profile: "conservative" });
    const post = calls.find((c) => c.url.includes("/dca/plan"));
    expect(post).toBeDefined();
    const body = JSON.parse(String(post!.init?.body));
    expect(body).not.toHaveProperty("current_score");
    expect(body.total_capital_irt).toBe(50000000);
  });

  it("exposes a shared recent-signals reader that maps 503 instead of failing silently (F2/F8)", async () => {
    installFetch((url) =>
      url.includes("/signals/recent")
        ? { status: 503, body: { success: false, error: "snapshot_unavailable" } }
        : { status: 200, body: { success: true, data: { signals: [] } } },
    );
    const { getRecentSignals, isServiceUnavailable } = await import("@/lib/goldApi");
    const err = await getRecentSignals(10).catch((e) => e);
    expect(isServiceUnavailable(err)).toBe(true);

    vi.unstubAllGlobals();
    installFetch(() => ({ status: 200, body: { success: true, data: { signals: [{ ts: 1 }] } } }));
    vi.resetModules();
    const mod = await import("@/lib/goldApi");
    await expect(mod.getRecentSignals(10)).resolves.toEqual([{ ts: 1 }]);
  });

  it("getStrategyBacktest calls /gold/backtest/strategy with the documented query", async () => {
    const { calls } = installFetch(() => ({
      status: 200,
      body: {
        success: true,
        data: {
          total_return_pct: 1,
          buy_hold_return_pct: 1,
          alpha_pct: 0,
          hit_rate_pct: 50,
          max_drawdown_pct: 1,
          sharpe_ratio: 1,
          n_successful: 1,
          n_trades: 1,
          final_value: 1,
          warning: null,
          trades: [],
        },
      },
    }));
    const { getStrategyBacktest } = await import("@/lib/goldApi");

    await getStrategyBacktest({ days: 90, bubble_trigger: 5, initial_capital: 100_000_000 });

    const call = calls.find((c) => c.url.includes("/gold/backtest/strategy"));
    expect(call).toBeDefined();
    expect(call!.url).toContain("days=90");
    expect(call!.url).toContain("bubble_trigger=5");
    expect(call!.url).toContain("initial_capital=100000000");
  });

  it("getHealth still reports which dependency is down when /health returns 503 (C8)", async () => {
    installFetch(() => ({
      status: 503,
      body: {
        brsapi_ok: true,
        redis_ok: false,
        db_ok: true,
        last_snapshot_at: null,
        scheduler_jobs: 0,
        telegram_configured: false,
        active_alert_rules: 0,
        unread_alerts: 0,
      },
    }));
    const { getHealth } = await import("@/lib/goldApi");
    const report = await getHealth();
    expect(report.redis_ok).toBe(false);
    expect(report.brsapi_ok).toBe(true);
  });
});
