// FE-14 — سه پروفایل کاربری (خرد / نهادی / اسکالپر) باید تعریفِ کامل و ثابت داشته باشند.

import { describe, expect, it } from "vitest";

import {
  DEFAULT_PERSONA,
  PERSONAS,
  PERSONA_IDS,
  isPersonaId,
  personaOrDefault,
} from "@/lib/personas";

describe("personas — definitions", () => {
  it("defines exactly the three supported personas", () => {
    expect(PERSONA_IDS).toEqual(["retail", "institutional", "scalper"]);
    expect(Object.keys(PERSONAS).sort()).toEqual([...PERSONA_IDS].sort());
  });

  it("labels each persona in Persian with a documented default view", () => {
    expect(PERSONAS.retail.label).toBe("خرد");
    expect(PERSONAS.institutional.label).toBe("نهادی");
    expect(PERSONAS.scalper.label).toBe("اسکالپر");

    for (const id of PERSONA_IDS) {
      const definition = PERSONAS[id];
      expect(definition.id).toBe(id);
      expect(definition.description.length).toBeGreaterThan(0);
      expect(definition.riskNote.length).toBeGreaterThan(0);
      expect(definition.defaultLandingPath.startsWith("/")).toBe(true);
      expect(definition.quickLinks.length).toBeGreaterThan(0);
      for (const link of definition.quickLinks) {
        expect(link.href.startsWith("/")).toBe(true);
        expect(link.label.length).toBeGreaterThan(0);
      }
    }
  });

  it("expresses the core differences through feature flags", () => {
    expect(PERSONAS.retail.features.marketRefreshMs).toBeGreaterThan(
      PERSONAS.institutional.features.marketRefreshMs,
    );
    expect(PERSONAS.institutional.features.marketRefreshMs).toBeGreaterThan(
      PERSONAS.scalper.features.marketRefreshMs,
    );
    expect(PERSONAS.retail.features.showFundamentals).toBe(false);
    expect(PERSONAS.institutional.features.showFundamentals).toBe(true);
    expect(PERSONAS.scalper.features.showOrderFlow).toBe(true);
    expect(PERSONAS.retail.features.denseLayout).toBe(false);
    expect(PERSONAS.scalper.features.denseLayout).toBe(true);
  });

  it("falls back to the retail persona for unknown values", () => {
    expect(DEFAULT_PERSONA).toBe("retail");
    expect(isPersonaId("scalper")).toBe(true);
    expect(isPersonaId("admin")).toBe(false);
    expect(isPersonaId(null)).toBe(false);
    expect(personaOrDefault("nope")).toBe("retail");
    expect(personaOrDefault("institutional")).toBe("institutional");
  });
});
