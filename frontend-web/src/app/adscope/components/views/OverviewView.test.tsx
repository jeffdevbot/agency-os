/**
 * @vitest-environment jsdom
 */
/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OverviewView } from "./OverviewView";
import type { OverviewView as Overview } from "../../types";

describe("OverviewView", () => {
  const mockData: Overview = {
    spend: 5000,
    sales: 20000,
    acos: 0.25,
    roas: 4.0,
    impressions: 100000,
    clicks: 5000,
    orders: 400,
    ad_type_mix: [
      { type: "Sponsored Products", spend: 3500, percentage: 0.70 },
      { type: "Sponsored Brands", spend: 1000, percentage: 0.20 },
      { type: "Sponsored Display", spend: 500, percentage: 0.10 },
    ],
    targeting_mix: {
      manual_spend: 3000,
      auto_spend: 2000,
      manual_percent: 0.60,
    },
  };

  it("renders all KPI cards", () => {
    render(
      <OverviewView
        data={mockData}
        currency="USD"
        warnings={[]}
        dateRangeMismatch={false}
      />
    );

    expect(screen.getByText("Total Spend")).toBeInTheDocument();
    expect(screen.getByText("Total Sales")).toBeInTheDocument();
    expect(screen.getByText("ACOS")).toBeInTheDocument();
    expect(screen.getByText("ROAS")).toBeInTheDocument();
  });

  it("displays formatted currency values", () => {
    render(
      <OverviewView
        data={mockData}
        currency="USD"
        warnings={[]}
        dateRangeMismatch={false}
      />
    );

    expect(screen.getByText("$5,000.00")).toBeInTheDocument();
    expect(screen.getByText("$20,000.00")).toBeInTheDocument();
  });

  it("displays ACOS and ROAS correctly", () => {
    render(
      <OverviewView
        data={mockData}
        currency="USD"
        warnings={[]}
        dateRangeMismatch={false}
      />
    );

    expect(screen.getByText("25.0%")).toBeInTheDocument();
    expect(screen.getByText("4.00x")).toBeInTheDocument();
  });

  it("shows date range mismatch warning when present", () => {
    render(
      <OverviewView
        data={mockData}
        currency="USD"
        warnings={[]}
        dateRangeMismatch={true}
      />
    );

    expect(
      screen.getByText(/File date ranges do not match/i)
    ).toBeInTheDocument();
  });

  it("displays warnings when provided", () => {
    const warnings = ["Test warning 1", "Test warning 2"];
    render(
      <OverviewView
        data={mockData}
        currency="USD"
        warnings={warnings}
        dateRangeMismatch={false}
      />
    );

    expect(screen.getByText("Test warning 1")).toBeInTheDocument();
    expect(screen.getByText("Test warning 2")).toBeInTheDocument();
  });

  it("renders ad type mix breakdown", () => {
    render(
      <OverviewView
        data={mockData}
        currency="USD"
        warnings={[]}
        dateRangeMismatch={false}
      />
    );

    expect(screen.getByText("Ad Type Mix")).toBeInTheDocument();
    expect(screen.getByText("Sponsored Products")).toBeInTheDocument();
    expect(screen.getByText("Sponsored Brands")).toBeInTheDocument();
    expect(screen.getByText("Sponsored Display")).toBeInTheDocument();
    expect(screen.getByText("70.0%")).toBeInTheDocument();
    expect(screen.getByText("20.0%")).toBeInTheDocument();
    expect(screen.getByText("10.0%")).toBeInTheDocument();
  });

  it("renders targeting mix breakdown", () => {
    render(
      <OverviewView
        data={mockData}
        currency="USD"
        warnings={[]}
        dateRangeMismatch={false}
      />
    );

    expect(screen.getByText("Targeting Control")).toBeInTheDocument();
    expect(screen.getByText("Manual")).toBeInTheDocument();
    expect(screen.getByText("Auto")).toBeInTheDocument();
    expect(screen.getByText("60.0%")).toBeInTheDocument();
    expect(screen.getByText("40.0%")).toBeInTheDocument();
  });

  it("shows warning when auto targeting exceeds 50%", () => {
    const dataWithHighAuto: Overview = {
      ...mockData,
      targeting_mix: {
        manual_spend: 1500,
        auto_spend: 3500,
        manual_percent: 0.30,
      },
    };

    render(
      <OverviewView
        data={dataWithHighAuto}
        currency="USD"
        warnings={[]}
        dateRangeMismatch={false}
      />
    );

    expect(
      screen.getByText(/High auto spend/i)
    ).toBeInTheDocument();
  });

  it("renders conversion funnel metrics", () => {
    render(
      <OverviewView
        data={mockData}
        currency="USD"
        warnings={[]}
        dateRangeMismatch={false}
      />
    );

    expect(screen.getByText("Conversion Funnel")).toBeInTheDocument();
    expect(screen.getByText("100,000")).toBeInTheDocument(); // impressions
    expect(screen.getByText("5,000")).toBeInTheDocument(); // clicks
    expect(screen.getByText("400")).toBeInTheDocument(); // orders
  });
});
