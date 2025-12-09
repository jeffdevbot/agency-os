/// <reference types="vitest/globals" />
import { describe, it, expect } from "vitest";
import {
  formatCurrency,
  formatPercent,
  formatNumber,
  getCurrencySymbol,
  getStateBadgeColor,
} from "./utils";

describe("AdScope Utils", () => {
  describe("formatCurrency", () => {
    it("formats USD correctly with symbol", () => {
      expect(formatCurrency(1234.56, "USD")).toBe("$1,234.56");
    });

    it("formats EUR correctly with symbol", () => {
      expect(formatCurrency(1234.56, "EUR")).toBe("€1,234.56");
    });

    it("formats GBP correctly with symbol", () => {
      expect(formatCurrency(1234.56, "GBP")).toBe("£1,234.56");
    });

    it("handles zero correctly", () => {
      expect(formatCurrency(0, "USD")).toBe("$0.00");
    });

    it("handles large numbers with proper comma separation", () => {
      expect(formatCurrency(1234567.89, "USD")).toBe("$1,234,567.89");
    });

    it("handles negative numbers", () => {
      expect(formatCurrency(-500.25, "USD")).toBe("$-500.25");
    });
  });

  describe("formatPercent", () => {
    it("formats percentage with default decimals", () => {
      expect(formatPercent(0.1234)).toBe("12.3%");
    });

    it("formats percentage with custom decimals", () => {
      expect(formatPercent(0.1234, 2)).toBe("12.34%");
    });

    it("formats percentage with 0 decimals", () => {
      expect(formatPercent(0.1234, 0)).toBe("12%");
    });

    it("handles zero correctly", () => {
      expect(formatPercent(0)).toBe("0.0%");
    });

    it("handles 100% correctly", () => {
      expect(formatPercent(1)).toBe("100.0%");
    });

    it("handles values over 100%", () => {
      expect(formatPercent(1.5, 1)).toBe("150.0%");
    });
  });

  describe("formatNumber", () => {
    it("formats numbers with commas", () => {
      expect(formatNumber(1234)).toBe("1,234");
    });

    it("formats large numbers", () => {
      expect(formatNumber(1234567)).toBe("1,234,567");
    });

    it("handles zero", () => {
      expect(formatNumber(0)).toBe("0");
    });

    it("rounds decimals to whole numbers", () => {
      expect(formatNumber(1234.56)).toBe("1,235");
    });
  });

  describe("getCurrencySymbol", () => {
    it("returns $ for USD", () => {
      expect(getCurrencySymbol("USD")).toBe("$");
    });

    it("returns € for EUR", () => {
      expect(getCurrencySymbol("EUR")).toBe("€");
    });

    it("returns £ for GBP", () => {
      expect(getCurrencySymbol("GBP")).toBe("£");
    });

    it("returns $ for unknown currency", () => {
      expect(getCurrencySymbol("XYZ")).toBe("$");
    });
  });

  describe("getStateBadgeColor", () => {
    it("returns green for enabled", () => {
      expect(getStateBadgeColor("enabled")).toBe("text-emerald-400 bg-emerald-500/20");
    });

    it("returns gray for paused", () => {
      expect(getStateBadgeColor("paused")).toBe("text-slate-400 bg-slate-500/20");
    });

    it("returns darker gray for archived", () => {
      expect(getStateBadgeColor("archived")).toBe("text-slate-500 bg-slate-600/20");
    });

    it("returns gray for unknown state", () => {
      expect(getStateBadgeColor("unknown")).toBe("text-slate-400 bg-slate-500/20");
    });
  });
});
