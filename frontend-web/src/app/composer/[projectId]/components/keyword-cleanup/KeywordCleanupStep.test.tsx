/**
 * @vitest-environment jsdom
 */
/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { KeywordCleanupStep } from "./KeywordCleanupStep";
import type { ComposerProject, ComposerKeywordPool } from "@agency/lib/composer/types";
import { useKeywordPools } from "@/lib/composer/hooks/useKeywordPools";
import { useSkuGroups } from "@/lib/composer/hooks/useSkuGroups";

// Mock hooks
vi.mock("@/lib/composer/hooks/useKeywordPools");
vi.mock("@/lib/composer/hooks/useSkuGroups");

// Mock child components to simplify testing
vi.mock("./CleanedKeywordsList", () => ({
    CleanedKeywordsList: ({ keywords }: { keywords: string[] }) => (
        <div data-testid="cleaned-list">Cleaned: {keywords.length}</div>
    ),
}));

vi.mock("./RemovedKeywordsList", () => ({
    RemovedKeywordsList: ({ removed }: { removed: any[] }) => (
        <div data-testid="removed-list">Removed: {removed.length}</div>
    ),
}));

describe.skip("KeywordCleanupStep (Composer)", () => {
    const mockProject: ComposerProject = {
        id: "proj-1",
        organizationId: "org-1",
        projectName: "Test Project",
        strategyType: "variations",
        createdAt: "2025-01-01",
    } as unknown as ComposerProject;

    const basePool: ComposerKeywordPool = {
        id: "pool-1",
        organizationId: "org-1",
        projectId: "proj-1",
        groupId: null,
        poolType: "body",
        status: "uploaded",
        rawKeywords: ["one", "two", "three", "four", "five"],
        cleanedKeywords: [],
        removedKeywords: [],
        cleanSettings: {},
        groupingConfig: {},
        cleanedAt: null,
        groupedAt: null,
        approvedAt: null,
        createdAt: "2025-01-01",
    };

    const defaultHooks = {
        pools: [basePool],
        isLoading: false,
        error: null,
        cleanPool: vi.fn(),
        manualRemove: vi.fn(),
        manualRestore: vi.fn(),
        approveClean: vi.fn(),
        unapproveClean: vi.fn(),
        refresh: vi.fn(),
    };

    const createHookState = (overrides: Partial<typeof defaultHooks> = {}) => ({
        ...defaultHooks,
        ...overrides,
    });

    beforeEach(() => {
        vi.resetAllMocks();
        vi.mocked(useKeywordPools).mockReturnValue(createHookState());
        vi.mocked(useSkuGroups).mockReturnValue({ groups: [], isLoading: false } as any);
    });

    it("renders default state with Description tab active", () => {
        vi.mocked(useSkuGroups).mockReturnValue({ groups: [], isLoading: false } as any);

        render(<KeywordCleanupStep project={mockProject} />);

        const descTab = screen.getByRole("button", { name: "Description & Bullets" });
        const titlesTab = screen.getByRole("button", { name: "Titles" });

        expect(descTab).toBeInTheDocument();
        expect(titlesTab).toBeInTheDocument();
        expect(descTab).toHaveClass("border-[#0a6fd6]");
    });

    it("switches tabs when clicked", async () => {
        const titlesPool = {
            ...basePool,
            id: "pool-2",
            poolType: "titles" as const,
            cleanedKeywords: ["title1"]
        };
        vi.mocked(useKeywordPools).mockReturnValue(
            createHookState({ pools: [basePool, titlesPool] }) as any,
        );

        render(<KeywordCleanupStep project={mockProject} />);

        // Initially body pool (0 cleaned)
        expect(screen.getByTestId("cleaned-list")).toHaveTextContent("Cleaned: 0");

        const titlesTabButton = screen.getByRole("button", { name: "Titles" });
        fireEvent.click(titlesTabButton);

        await waitFor(() => {
            // Should show titles pool (1 cleaned)
            expect(screen.getByTestId("cleaned-list")).toHaveTextContent("Cleaned: 1");
            expect(titlesTabButton).toHaveClass("border-[#0a6fd6]");
        });
    });

    it("shows correct progress indicator for uploaded state", () => {
        vi.mocked(useKeywordPools).mockReturnValue(
            createHookState({ pools: [{ ...basePool, status: "uploaded" }] }) as any,
        );

        render(<KeywordCleanupStep project={mockProject} />);

        const reviewLabel = screen.getByText("Review & Edit");
        expect(reviewLabel).toHaveClass("text-[#94a3b8]");
    });

    it("shows correct progress indicator for cleaned state", () => {
        vi.mocked(useKeywordPools).mockReturnValue(
            createHookState({
                pools: [{ ...basePool, status: "cleaned", cleanedKeywords: ["one", "two", "three", "four", "five"] }],
            }) as any,
        );

        render(<KeywordCleanupStep project={mockProject} />);

        const reviewLabel = screen.getByText("Review & Edit");
        expect(reviewLabel).toHaveClass("text-[#16a34a]");
    });

    it("approves pool when button clicked and confirmed", async () => {
        const approveCleanMock = vi.fn();
        const refreshMock = vi.fn();
        const approvablePool = {
            ...basePool,
            cleanedKeywords: ["one", "two", "three", "four", "five"],
            status: "uploaded" as const,
        };
        vi.mocked(useKeywordPools).mockReturnValue(
            createHookState({
                approveClean: approveCleanMock,
                refresh: refreshMock,
                pools: [approvablePool],
            }) as any,
        );

        render(<KeywordCleanupStep project={mockProject} />);

        const approveBtn = screen.getByRole("button", { name: /Approve This Pool/i });
        fireEvent.click(approveBtn);

        // Should show confirmation checkbox
        const checkbox = screen.getByRole("checkbox", { name: /reviewed the cleaned and removed keywords/i });
        fireEvent.click(checkbox);

        fireEvent.click(approveBtn);

        await waitFor(() => {
            expect(approveCleanMock).toHaveBeenCalledWith("pool-1");
            expect(refreshMock).toHaveBeenCalled();
        });
    });

    it("shows approved state and allows unapproval", async () => {
        const unapproveCleanMock = vi.fn();
        const refreshMock = vi.fn();
        vi.mocked(useKeywordPools).mockReturnValue(
            createHookState({
                unapproveClean: unapproveCleanMock,
                refresh: refreshMock,
                pools: [{ ...basePool, status: "cleaned", cleanedKeywords: ["one", "two", "three", "four", "five"], approvedAt: "2025-01-01" }],
            }) as any,
        );

        render(<KeywordCleanupStep project={mockProject} />);

        const approvedBtn = screen.getByRole("button", { name: /Approved/i });
        expect(approvedBtn).toBeInTheDocument();

        fireEvent.click(approvedBtn);

        await waitFor(() => {
            expect(unapproveCleanMock).toHaveBeenCalledWith("pool-1");
            expect(refreshMock).toHaveBeenCalled();
        });
    });

    it("shows 'Continue to Titles' button only when body is approved", async () => {
        const approvedBody = {
            ...basePool,
            cleanedKeywords: ["one", "two", "three", "four", "five"],
            status: "cleaned" as const
        };
        const titlesPool = {
            ...basePool,
            id: "pool-2",
            poolType: "titles" as const,
            cleanedKeywords: ["title1"]
        };

        vi.mocked(useKeywordPools).mockReturnValue(
            createHookState({ pools: [approvedBody, titlesPool] }) as any,
        );

        render(<KeywordCleanupStep project={mockProject} />);

        const continueBtn = screen.getByRole("button", { name: /Continue to Titles Pool/i });
        expect(continueBtn).toBeInTheDocument();

        fireEvent.click(continueBtn);

        // Should switch tab to titles
        await waitFor(() => {
            expect(screen.getByTestId("cleaned-list")).toHaveTextContent("Cleaned: 1");
            const titlesTab = screen.getByRole("button", { name: "Titles" });
            expect(titlesTab).toHaveClass("border-[#0a6fd6]");
        });
    });
});
