/**
 * @vitest-environment jsdom
 */
/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WasteBinView } from "./WasteBinView";
import type { WasteBinItem } from "../../types";

describe("WasteBinView", () => {
  const mockWasteData: WasteBinItem[] = [
    {
      search_term: "expensive keyword",
      spend: 150.0,
      impressions: 500,
      clicks: 20,
    },
    {
      search_term: "another waste",
      spend: 75.5,
      impressions: 300,
      clicks: 10,
    },
  ];

  it("renders header and description", () => {
    render(<WasteBinView data={mockWasteData} currency="USD" />);

    expect(screen.getByText("Waste Bin")).toBeInTheDocument();
    expect(
      screen.getByText(/Search terms with spend/i)
    ).toBeInTheDocument();
  });

  it("displays empty state when no waste found", () => {
    render(<WasteBinView data={[]} currency="USD" />);

    expect(screen.getByText("No wasted spend found")).toBeInTheDocument();
    expect(
      screen.getByText(/No search terms with spend but zero sales/i)
    ).toBeInTheDocument();
  });

  it("renders waste bin items when data is present", () => {
    render(<WasteBinView data={mockWasteData} currency="USD" />);

    expect(screen.getByText("expensive keyword")).toBeInTheDocument();
    expect(screen.getByText("another waste")).toBeInTheDocument();
  });

  it("displays formatted spend values", () => {
    render(<WasteBinView data={mockWasteData} currency="USD" />);

    expect(screen.getByText("$150.00")).toBeInTheDocument();
    expect(screen.getByText("$75.50")).toBeInTheDocument();
  });

  it("displays clicks in table", () => {
    render(<WasteBinView data={mockWasteData} currency="USD" />);

    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  it("formats currency based on currency code", () => {
    render(<WasteBinView data={mockWasteData} currency="EUR" />);

    expect(screen.getByText("€150.00")).toBeInTheDocument();
    expect(screen.getByText("€75.50")).toBeInTheDocument();
  });

  it("handles single waste item correctly", () => {
    const singleItem: WasteBinItem[] = [
      {
        search_term: "single waste",
        spend: 100.0,
        impressions: 200,
        clicks: 5,
      },
    ];

    render(<WasteBinView data={singleItem} currency="USD" />);

    expect(screen.getByText("single waste")).toBeInTheDocument();
    expect(screen.getByText("$100.00")).toBeInTheDocument();
  });
});
