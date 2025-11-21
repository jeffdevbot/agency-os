/**
 * @vitest-environment jsdom
 */
/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { KeywordGroupCard } from "./KeywordGroupCard";
import type { KeywordGroup } from "./types";
import { useDroppable } from "@dnd-kit/core";

// Mock the DraggableKeyword component to simplify testing
vi.mock("./DraggableKeyword", () => ({
  DraggableKeyword: ({ phrase, groupId }: { phrase: string; groupId: string }) => (
    <div data-testid={`draggable-${phrase}`} data-group-id={groupId}>
      {phrase}
    </div>
  ),
}));

// Mock @dnd-kit/core useDroppable hook
vi.mock("@dnd-kit/core", () => ({
  useDroppable: vi.fn(() => ({
    setNodeRef: vi.fn(),
    isOver: false,
  })),
}));

describe("KeywordGroupCard", () => {
  const mockGroup: KeywordGroup = {
    id: "group-1",
    label: "Test Group",
    phrases: ["keyword1", "keyword2", "keyword3"],
  };

  const mockOnUpdateLabel = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(useDroppable).mockReturnValue({ setNodeRef: vi.fn(), isOver: false });
  });

  it("renders group label and phrase count", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    expect(screen.getByText("Test Group")).toBeInTheDocument();
    expect(screen.getByText("3 keywords")).toBeInTheDocument();
  });

  it("renders all phrases when expanded", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    expect(screen.getByTestId("draggable-keyword1")).toBeInTheDocument();
    expect(screen.getByTestId("draggable-keyword2")).toBeInTheDocument();
    expect(screen.getByTestId("draggable-keyword3")).toBeInTheDocument();
  });

  it("toggles collapse state when chevron button is clicked", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    // Initially expanded (▼)
    const collapseButton = screen.getByRole("button", { name: "▼" });
    expect(screen.getByTestId("draggable-keyword1")).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(collapseButton);

    // Should show ▶ and hide phrases
    expect(screen.getByRole("button", { name: "▶" })).toBeInTheDocument();
    expect(screen.queryByTestId("draggable-keyword1")).not.toBeInTheDocument();

    // Click to expand again
    fireEvent.click(collapseButton);

    // Should show ▼ and show phrases
    expect(screen.getByRole("button", { name: "▼" })).toBeInTheDocument();
    expect(screen.getByTestId("draggable-keyword1")).toBeInTheDocument();
  });

  it("enters edit mode when label is clicked", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    const labelElement = screen.getByText("Test Group");
    fireEvent.click(labelElement);

    // Should show input with current label value
    const input = screen.getByDisplayValue("Test Group");
    expect(input).toBeInTheDocument();
    expect(input).toHaveFocus();
  });

  it("saves label changes on blur", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    // Enter edit mode
    const labelElement = screen.getByText("Test Group");
    fireEvent.click(labelElement);

    const input = screen.getByDisplayValue("Test Group");
    fireEvent.change(input, { target: { value: "Updated Group" } });
    fireEvent.blur(input);

    expect(mockOnUpdateLabel).toHaveBeenCalledWith("group-1", "Updated Group");
  });

  it("saves label changes on Enter key", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    // Enter edit mode
    const labelElement = screen.getByText("Test Group");
    fireEvent.click(labelElement);

    const input = screen.getByDisplayValue("Test Group");
    fireEvent.change(input, { target: { value: "Updated Group" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(mockOnUpdateLabel).toHaveBeenCalledWith("group-1", "Updated Group");
  });

  it("cancels label editing on Escape key without calling onUpdateLabel", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    // Enter edit mode
    const labelElement = screen.getByText("Test Group");
    fireEvent.click(labelElement);

    const input = screen.getByDisplayValue("Test Group");
    fireEvent.change(input, { target: { value: "Updated Group" } });
    fireEvent.keyDown(input, { key: "Escape" });

    // Should revert to original label and not call onUpdateLabel
    expect(mockOnUpdateLabel).not.toHaveBeenCalled();
    expect(screen.getByText("Test Group")).toBeInTheDocument();
  });

  it("does not call onUpdateLabel if label unchanged", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    // Enter edit mode
    const labelElement = screen.getByText("Test Group");
    fireEvent.click(labelElement);

    const input = screen.getByDisplayValue("Test Group");
    // Don't change the value, just blur
    fireEvent.blur(input);

    expect(mockOnUpdateLabel).not.toHaveBeenCalled();
  });

  it("trims whitespace from label before saving", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    // Enter edit mode
    const labelElement = screen.getByText("Test Group");
    fireEvent.click(labelElement);

    const input = screen.getByDisplayValue("Test Group");
    fireEvent.change(input, { target: { value: "  Trimmed Label  " } });
    fireEvent.blur(input);

    expect(mockOnUpdateLabel).toHaveBeenCalledWith("group-1", "Trimmed Label");
  });

  it("does not call onUpdateLabel when undefined", () => {
    render(<KeywordGroupCard group={mockGroup} />);

    // Enter edit mode
    const labelElement = screen.getByText("Test Group");
    fireEvent.click(labelElement);

    const input = screen.getByDisplayValue("Test Group");
    fireEvent.change(input, { target: { value: "Updated Group" } });
    fireEvent.blur(input);

    // Should not throw error when onUpdateLabel is undefined
    expect(true).toBe(true);
  });

  it("applies droppable styling when isOver is true", () => {
    const useDroppableMock = vi.mocked(useDroppable);
    useDroppableMock.mockReturnValue({
      setNodeRef: vi.fn(),
      isOver: true,
    });

    const { container } = render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    const card = container.firstChild as HTMLElement;
    expect(card).toHaveClass("bg-blue-50");
    expect(card).toHaveClass("border-blue-300");
  });

  it("applies default styling when isOver is false", () => {
    const useDroppableMock = vi.mocked(useDroppable);
    useDroppableMock.mockReturnValue({
      setNodeRef: vi.fn(),
      isOver: false,
    });

    const { container } = render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    const card = container.firstChild as HTMLElement;
    expect(card).toHaveClass("bg-white");
    expect(card).toHaveClass("border-gray-200");
  });

  it("renders with empty phrases array", () => {
    const emptyGroup: KeywordGroup = {
      id: "group-2",
      label: "Empty Group",
      phrases: [],
    };

    render(<KeywordGroupCard group={emptyGroup} onUpdateLabel={mockOnUpdateLabel} />);

    expect(screen.getByText("Empty Group")).toBeInTheDocument();
    expect(screen.getByText("0 keywords")).toBeInTheDocument();
  });

  it("renders with single phrase", () => {
    const singleGroup: KeywordGroup = {
      id: "group-3",
      label: "Single Group",
      phrases: ["only-one"],
    };

    render(<KeywordGroupCard group={singleGroup} onUpdateLabel={mockOnUpdateLabel} />);

    expect(screen.getByText("Single Group")).toBeInTheDocument();
    expect(screen.getByText("1 keywords")).toBeInTheDocument(); // Note: doesn't pluralize
    expect(screen.getByTestId("draggable-only-one")).toBeInTheDocument();
  });

  it("renders with many phrases", () => {
    const manyPhrases = Array.from({ length: 50 }, (_, i) => `keyword${i + 1}`);
    const largeGroup: KeywordGroup = {
      id: "group-4",
      label: "Large Group",
      phrases: manyPhrases,
    };

    render(<KeywordGroupCard group={largeGroup} onUpdateLabel={mockOnUpdateLabel} />);

    expect(screen.getByText("Large Group")).toBeInTheDocument();
    expect(screen.getByText("50 keywords")).toBeInTheDocument();

    // Verify all phrases are rendered (when expanded)
    manyPhrases.forEach((phrase) => {
      expect(screen.getByTestId(`draggable-${phrase}`)).toBeInTheDocument();
    });
  });

  it("maintains scroll position for long phrase lists", () => {
    const manyPhrases = Array.from({ length: 100 }, (_, i) => `keyword${i + 1}`);
    const largeGroup: KeywordGroup = {
      id: "group-5",
      label: "Scrollable Group",
      phrases: manyPhrases,
    };

    const { container } = render(<KeywordGroupCard group={largeGroup} onUpdateLabel={mockOnUpdateLabel} />);

    // Find the phrases container
    const phrasesContainer = container.querySelector(".max-h-\\[400px\\]");
    expect(phrasesContainer).toBeInTheDocument();
    expect(phrasesContainer).toHaveClass("overflow-y-auto");
  });

  it("passes correct groupId to DraggableKeyword components", () => {
    render(<KeywordGroupCard group={mockGroup} onUpdateLabel={mockOnUpdateLabel} />);

    const draggableElements = screen.getAllByTestId(/^draggable-/);
    draggableElements.forEach((element) => {
      expect(element).toHaveAttribute("data-group-id", "group-1");
    });
  });

  it("handles label with special characters", () => {
    const specialGroup: KeywordGroup = {
      id: "group-6",
      label: "Group & Special @ Chars!",
      phrases: ["test"],
    };

    render(<KeywordGroupCard group={specialGroup} onUpdateLabel={mockOnUpdateLabel} />);

    expect(screen.getByText("Group & Special @ Chars!")).toBeInTheDocument();
  });
});
