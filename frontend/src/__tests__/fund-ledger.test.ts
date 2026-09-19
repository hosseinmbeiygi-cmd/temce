/**
 * Unit tests for fund-ledger pure helpers.
 */

import { describe, expect, it } from "vitest";
import {
  ACCOUNT_TYPE_LABELS,
  ENTRY_STATUS_LABELS,
  MOVEMENT_TYPE_LABELS,
  accountTone,
  formatAmount,
  isBalanced,
  movementTone,
  type TrialBalance,
} from "@/lib/fund-ledger";
import { labelOf } from "@/lib/fund-nav";

describe("fund-ledger helpers", () => {
  it("maps account type to tone", () => {
    expect(accountTone("ASSET")).toBe("pos");
    expect(accountTone("LIABILITY")).toBe("warn");
    expect(accountTone("EXPENSE")).toBe("neg");
    expect(accountTone("EQUITY")).toBe("default");
  });

  it("maps movement type to tone", () => {
    expect(movementTone("ISSUE")).toBe("pos");
    expect(movementTone("REDEEM")).toBe("warn");
    expect(movementTone("DISTRIBUTION")).toBe("default");
  });

  it("labels are complete and readable", () => {
    expect(labelOf(MOVEMENT_TYPE_LABELS, "ISSUE")).toBe("صدور");
    expect(labelOf(ACCOUNT_TYPE_LABELS, "EQUITY")).toBe("حقوق واحدها");
    expect(labelOf(ENTRY_STATUS_LABELS, "POSTED")).toBe("ثبت‌شده");
  });

  it("formats amounts and checks balance", () => {
    expect(formatAmount(null)).toBe("—");
    expect(formatAmount(1000)).not.toBe("—");
    const trial: TrialBalance = {
      accounts: [],
      total_debit: 100,
      total_credit: 100,
      balanced: true,
    };
    expect(isBalanced(trial)).toBe(true);
    expect(isBalanced(null)).toBe(false);
    expect(isBalanced({ ...trial, balanced: false })).toBe(false);
  });
});
