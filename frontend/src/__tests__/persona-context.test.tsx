// FE-14 — انتخاب پروفایل کاربری: پیش‌فرض خرد، ماندگاری، و تغییر نمای داشبورد.

import { beforeEach, describe, expect, it } from "vitest";
import { render, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";

import { PersonaProvider, usePersona } from "@/lib/persona-context";
import { PERSONA_STORAGE_KEY } from "@/lib/personas";
import PersonaSwitcher from "@/components/layout/PersonaSwitcher";
import PersonaBar from "@/components/dashboard/PersonaBar";

function wrapper({ children }: { children: ReactNode }) {
  return <PersonaProvider>{children}</PersonaProvider>;
}

beforeEach(() => {
  localStorage.clear();
});

describe("PersonaProvider", () => {
  it("defaults to the retail persona when nothing is stored", async () => {
    const { result } = renderHook(() => usePersona(), { wrapper });

    expect(result.current.persona).toBe("retail");
    expect(result.current.definition.label).toBe("خرد");
    await waitFor(() => expect(result.current.ready).toBe(true));
  });

  it("adopts the stored persona after mount (SSR-safe)", async () => {
    localStorage.setItem(PERSONA_STORAGE_KEY, "scalper");

    const { result } = renderHook(() => usePersona(), { wrapper });

    await waitFor(() => expect(result.current.persona).toBe("scalper"));
    expect(result.current.definition.defaultLandingPath).toBe("/market-depth");
  });

  it("persists the choice and ignores unknown stored values", async () => {
    localStorage.setItem(PERSONA_STORAGE_KEY, "admin");

    const { result } = renderHook(() => usePersona(), { wrapper });
    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.persona).toBe("retail");

    result.current.setPersona("institutional");
    expect(localStorage.getItem(PERSONA_STORAGE_KEY)).toBe("institutional");
    await waitFor(() => expect(result.current.definition.label).toBe("نهادی"));
  });
});

describe("persona UI", () => {
  it("switches the dashboard strip and shortcuts with the navbar selector", async () => {
    const user = userEvent.setup();
    render(
      <PersonaProvider>
        <PersonaSwitcher />
        <PersonaBar />
      </PersonaProvider>,
    );

    // Retail default: gold/funds shortcuts, no portfolio shortcut.
    expect(screen.getByRole("navigation", { name: "دسترسی سریع نمای کاربری" })).toHaveTextContent("بازار طلا");
    expect(screen.queryByRole("link", { name: "پرتفوی" })).toBeNull();

    await user.selectOptions(screen.getByRole("combobox", { name: "پروفایل کاربری" }), "institutional");

    expect(screen.getByRole("link", { name: "پرتفوی" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "بنیادی" })).toBeInTheDocument();
    const strip = screen.getByRole("region", { name: "نمای کاربری" });
    expect(within(strip).getByText("نهادی")).toBeInTheDocument();
    expect(localStorage.getItem(PERSONA_STORAGE_KEY)).toBe("institutional");
  });

  it("renders the retail persona outside a provider instead of crashing", () => {
    render(<PersonaBar />);
    expect(screen.getByText("خرد")).toBeInTheDocument();
  });
});
