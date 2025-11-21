/**
 * @vitest-environment jsdom
 */
/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RemovedKeywordsList } from "./RemovedKeywordsList";
import type { RemovedKeywordEntry } from "@agency/lib/composer/types";

describe("RemovedKeywordsList", () => {
    const mockRemoved: RemovedKeywordEntry[] = [
        { term: "duplicate1", reason: "duplicate" },
        { term: "duplicate2", reason: "duplicate" },
        { term: "color1", reason: "color" },
        { term: "manual1", reason: "manual" },
    ];
    const mockOnRestore = vi.fn();

    it("renders nothing when removed list is empty", () => {
        const { container } = render(
            <RemovedKeywordsList removed={[]} onRestore={mockOnRestore} />
        );
        expect(container).toBeEmptyDOMElement();
    });

    it("renders header with correct count and starts collapsed", () => {
        render(
            <RemovedKeywordsList removed={mockRemoved} onRestore={mockOnRestore} />
        );

        expect(screen.getByText("Removed Keywords (4)")).toBeInTheDocument();
        expect(screen.getByText("Keywords filtered out during cleanup")).toBeInTheDocument();
        expect(screen.getByText("▼")).toBeInTheDocument();

        // Content should not be visible
        expect(screen.queryByText("duplicate1")).not.toBeInTheDocument();
    });

    it("expands and shows grouped reasons", () => {
        render(
            <RemovedKeywordsList removed={mockRemoved} onRestore={mockOnRestore} />
        );

        const headerButton = screen.getByRole("button", { name: /Removed Keywords/i });
        fireEvent.click(headerButton);

        // Should show reason groups
        expect(screen.getByText("duplicate (2)")).toBeInTheDocument();
        expect(screen.getByText("color (1)")).toBeInTheDocument();
        expect(screen.getByText("manual (1)")).toBeInTheDocument();

        // Reasons should be collapsed by default
        expect(screen.queryByText("duplicate1")).not.toBeInTheDocument();
    });

    it("expands reason group and shows keywords", () => {
        render(
            <RemovedKeywordsList removed={mockRemoved} onRestore={mockOnRestore} />
        );

        // Expand main list
        fireEvent.click(screen.getByRole("button", { name: /Removed Keywords/i }));

        // Expand duplicate group
        const duplicateGroupButton = screen.getByRole("button", { name: /duplicate \(2\)/i });
        fireEvent.click(duplicateGroupButton);

        expect(screen.getByText("duplicate1")).toBeInTheDocument();
        expect(screen.getByText("duplicate2")).toBeInTheDocument();

        // Other groups should still be collapsed
        expect(screen.queryByText("color1")).not.toBeInTheDocument();
    });

    it("applies correct badge colors", () => {
        render(
            <RemovedKeywordsList removed={mockRemoved} onRestore={mockOnRestore} />
        );
        fireEvent.click(screen.getByRole("button", { name: /Removed Keywords/i }));

        const duplicateBadge = screen.getByText("duplicate", { selector: "span.rounded-full" });
        expect(duplicateBadge).toHaveClass("bg-gray-100");
        expect(duplicateBadge).toHaveClass("text-gray-700");

        const colorBadge = screen.getByText("color", { selector: "span.rounded-full" });
        expect(colorBadge).toHaveClass("bg-blue-100");
        expect(colorBadge).toHaveClass("text-blue-700");
    });

    it("calls onRestore when restore button is clicked", () => {
        render(
            <RemovedKeywordsList removed={mockRemoved} onRestore={mockOnRestore} />
        );

        // Expand main list
        fireEvent.click(screen.getByRole("button", { name: /Removed Keywords/i }));
        // Expand manual group
        fireEvent.click(screen.getByRole("button", { name: /manual \(1\)/i }));

        const restoreButton = screen.getByText("Restore");
        fireEvent.click(restoreButton);

        expect(mockOnRestore).toHaveBeenCalledWith("manual1");
    });

    it("shows correct total count in footer", () => {
        render(
            <RemovedKeywordsList removed={mockRemoved} onRestore={mockOnRestore} />
        );
        fireEvent.click(screen.getByRole("button", { name: /Removed Keywords/i }));

        expect(screen.getByText("Showing all 4 removed keywords")).toBeInTheDocument();
    });
});
