/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import "@testing-library/jest-dom";
import { render, screen, fireEvent } from "@testing-library/react";
import { SkuTopicsCard } from "./SkuTopicsCard";

describe("SkuTopicsCard", () => {
  const baseSku = { id: "sku-1", skuCode: "SKU-001", productName: "Product 1" };
  const makeTopic = (i: number, selected = false) => ({
    id: `t${i}`,
    skuId: baseSku.id,
    topicIndex: i,
    title: `Topic ${i}`,
    description: null,
    selected,
  });

  it("shows selected count and invokes toggle", () => {
    const topics = [makeTopic(1, true), makeTopic(2, false)];
    const onToggle = vi.fn();

    render(<SkuTopicsCard sku={baseSku} topics={topics} onToggleTopic={onToggle} />);

    expect(screen.getByText("1 / 5 selected")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/Topic 2/i));
    expect(onToggle).toHaveBeenCalledWith("t2");
  });

  it("indicates completion at 5 selected", () => {
    const topics = [1, 2, 3, 4, 5].map((i) => makeTopic(i, true));
    render(<SkuTopicsCard sku={baseSku} topics={topics} onToggleTopic={() => {}} />);
    expect(screen.getByText("5 / 5 selected")).toBeInTheDocument();
    expect(screen.getByTestId("complete-check") || screen.getByText("5 / 5 selected")).toBeTruthy();
  });
});
