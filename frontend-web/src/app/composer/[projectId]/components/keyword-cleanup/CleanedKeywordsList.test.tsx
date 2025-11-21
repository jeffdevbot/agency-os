/**
 * @vitest-environment jsdom
 */
/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CleanedKeywordsList } from "./CleanedKeywordsList";

describe("CleanedKeywordsList", () => {
    const mockKeywords = ["keyword1", "keyword2", "keyword3"];
    const mockOnRemove = vi.fn();

    it("renders nothing when keywords list is empty", () => {
        const { container } = render(
            <CleanedKeywordsList keywords={[]} onRemove={mockOnRemove} />
        );
        expect(container).toBeEmptyDOMElement();
    });

    it("renders header with correct count and starts collapsed", () => {
        render(
            <CleanedKeywordsList keywords={mockKeywords} onRemove={mockOnRemove} />
        );

        // Header should be visible
        expect(screen.getByText("Cleaned Keywords (3)")).toBeInTheDocument();
        expect(screen.getByText("Click to expand and review keywords")).toBeInTheDocument();

        // Chevron should indicate collapsed
        expect(screen.getByText("▼")).toBeInTheDocument();

        // Content should not be visible (queryByText returns null if not found)
        expect(screen.queryByText("keyword1")).not.toBeInTheDocument();
    });

    it("expands and collapses when header is clicked", () => {
        render(
            <CleanedKeywordsList keywords={mockKeywords} onRemove={mockOnRemove} />
        );

        const headerButton = screen.getByRole("button", { name: /Cleaned Keywords/i });

        // Click to expand
        fireEvent.click(headerButton);

        expect(screen.getByText("keyword1")).toBeInTheDocument();
        expect(screen.getByText("keyword2")).toBeInTheDocument();
        expect(screen.getByText("keyword3")).toBeInTheDocument();
        expect(screen.getByText("▲")).toBeInTheDocument();
        expect(screen.getByText("Click to collapse list")).toBeInTheDocument();

        // Click to collapse
        fireEvent.click(headerButton);

        expect(screen.queryByText("keyword1")).not.toBeInTheDocument();
        expect(screen.getByText("▼")).toBeInTheDocument();
    });

    it("calls onRemove when remove button is clicked", () => {
        render(
            <CleanedKeywordsList keywords={mockKeywords} onRemove={mockOnRemove} />
        );

        // Expand first
        fireEvent.click(screen.getByRole("button", { name: /Cleaned Keywords/i }));

        // Find remove buttons (they are rendered for each keyword)
        const removeButtons = screen.getAllByText("Remove");
        expect(removeButtons).toHaveLength(3);

        // Click remove on first keyword
        fireEvent.click(removeButtons[0]);

        expect(mockOnRemove).toHaveBeenCalledWith("keyword1");
    });

    it("shows correct total count in footer", () => {
        render(
            <CleanedKeywordsList keywords={mockKeywords} onRemove={mockOnRemove} />
        );

        // Expand first
        fireEvent.click(screen.getByRole("button", { name: /Cleaned Keywords/i }));

        expect(screen.getByText("Showing all 3 cleaned keywords")).toBeInTheDocument();
    });
});
