/**
 * @vitest-environment jsdom
 */
/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DraggableKeyword } from "./DraggableKeyword";
import { DndContext, useDraggable } from "@dnd-kit/core";

// Mock the useDraggable hook from @dnd-kit/core
vi.mock("@dnd-kit/core", async () => {
  const actual = await vi.importActual<typeof import("@dnd-kit/core")>("@dnd-kit/core");
  return {
    ...actual,
    useDraggable: vi.fn(() => ({
      attributes: { role: "button", tabIndex: 0, "aria-describedby": "draggable-item" },
      listeners: { onPointerDown: vi.fn() },
      setNodeRef: vi.fn(),
      transform: null,
      isDragging: false,
    })),
  };
});

describe("DraggableKeyword", () => {
  const defaultProps = {
    phrase: "test keyword",
    groupId: "group-1",
  };

  it("renders the keyword phrase", () => {
    render(<DraggableKeyword {...defaultProps} />);

    expect(screen.getByText("test keyword")).toBeInTheDocument();
  });

  it("applies correct base styling", () => {
    render(<DraggableKeyword {...defaultProps} />);

    const element = screen.getByText("test keyword");
    expect(element).toHaveClass("px-3");
    expect(element).toHaveClass("py-1.5");
    expect(element).toHaveClass("bg-gray-100");
    expect(element).toHaveClass("rounded-md");
    expect(element).toHaveClass("text-sm");
    expect(element).toHaveClass("cursor-move");
  });

  it("has draggable attributes", () => {
    render(<DraggableKeyword {...defaultProps} />);

    const element = screen.getByText("test keyword");
    expect(element).toHaveAttribute("role", "button");
    expect(element).toHaveAttribute("tabIndex", "0");
  });

  it("renders with correct group context", () => {
    render(<DraggableKeyword phrase="blue" groupId="group-2" />);

    const useDraggableMock = vi.mocked(useDraggable);
    expect(useDraggableMock).toHaveBeenCalledWith({
      id: "blue",
      data: { phrase: "blue", groupId: "group-2" },
    });
  });

  it("applies dragging state styling", () => {
    const useDraggableMock = vi.mocked(useDraggable);
    useDraggableMock.mockReturnValue({
      attributes: { role: "button", tabIndex: 0 },
      listeners: { onPointerDown: vi.fn() },
      setNodeRef: vi.fn(),
      transform: { x: 10, y: 20, scaleX: 1, scaleY: 1 },
      isDragging: true,
    });

    render(<DraggableKeyword {...defaultProps} />);

    const element = screen.getByText("test keyword");
    // When isDragging is true, opacity should be 0.5
    expect(element).toHaveStyle({ opacity: 0.5 });
  });

  it("applies transform when dragging", () => {
    const useDraggableMock = vi.mocked(useDraggable);
    useDraggableMock.mockReturnValue({
      attributes: { role: "button", tabIndex: 0 },
      listeners: { onPointerDown: vi.fn() },
      setNodeRef: vi.fn(),
      transform: { x: 50, y: 100, scaleX: 1, scaleY: 1 },
      isDragging: true,
    });

    render(<DraggableKeyword {...defaultProps} />);

    const element = screen.getByText("test keyword");
    expect(element).toHaveStyle({ transform: "translate3d(50px, 100px, 0)" });
  });

  it("renders within DndContext correctly", () => {
    render(
      <DndContext>
        <DraggableKeyword phrase="context keyword" groupId="group-3" />
      </DndContext>
    );

    expect(screen.getByText("context keyword")).toBeInTheDocument();
  });

  it("handles special characters in phrase", () => {
    render(<DraggableKeyword phrase="keyword & special @ chars!" groupId="group-1" />);

    expect(screen.getByText("keyword & special @ chars!")).toBeInTheDocument();
  });

  it("handles long keyword phrases", () => {
    const longPhrase = "This is a very long keyword phrase that might wrap to multiple lines in the UI";
    render(<DraggableKeyword phrase={longPhrase} groupId="group-1" />);

    expect(screen.getByText(longPhrase)).toBeInTheDocument();
  });

  it("renders multiple draggable keywords without conflicts", () => {
    const { container } = render(
      <div>
        <DraggableKeyword phrase="keyword 1" groupId="group-1" />
        <DraggableKeyword phrase="keyword 2" groupId="group-1" />
        <DraggableKeyword phrase="keyword 3" groupId="group-2" />
      </div>
    );

    expect(screen.getByText("keyword 1")).toBeInTheDocument();
    expect(screen.getByText("keyword 2")).toBeInTheDocument();
    expect(screen.getByText("keyword 3")).toBeInTheDocument();
    expect(container.querySelectorAll(".cursor-move")).toHaveLength(3);
  });

  it("applies hover styling class", () => {
    render(<DraggableKeyword {...defaultProps} />);

    const element = screen.getByText("test keyword");
    expect(element).toHaveClass("hover:bg-gray-200");
  });

  it("applies transition styling class", () => {
    render(<DraggableKeyword {...defaultProps} />);

    const element = screen.getByText("test keyword");
    expect(element).toHaveClass("transition-colors");
  });
});
