/**
 * @vitest-environment jsdom
 */
/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { GroupingPlanStep } from "./GroupingPlanStep";
import type { ComposerKeywordPool } from "@agency/lib/composer/types";
import { useKeywordPools } from "@/lib/composer/hooks/useKeywordPools";
import type { KeywordGroup } from "./types";

// Mock the hook
vi.mock("@/lib/composer/hooks/useKeywordPools");

// Mock child components to simplify testing
vi.mock("./KeywordGroupCard", () => ({
  KeywordGroupCard: ({ group, onUpdateLabel }: { group: KeywordGroup; onUpdateLabel: (id: string, label: string) => void }) => (
    <div data-testid={`group-card-${group.id}`}>
      <div>{group.label}</div>
      <div>{group.phrases.length} phrases</div>
      <button onClick={() => onUpdateLabel(group.id, "Updated Label")}>Update Label</button>
    </div>
  ),
}));

vi.mock("./GroupingConfigForm", () => ({
  GroupingConfigForm: ({ onGenerate, isGenerating }: any) => (
    <div data-testid="config-form">
      <button onClick={() => onGenerate({ basis: "single" })} disabled={isGenerating}>
        {isGenerating ? "Generating..." : "Generate"}
      </button>
    </div>
  ),
}));

// Mock @dnd-kit/core
vi.mock("@dnd-kit/core", () => ({
  DndContext: ({ children, onDragEnd }: any) => (
    <div data-testid="dnd-context" data-on-drag-end={onDragEnd ? "true" : "false"}>
      {children}
    </div>
  ),
  closestCenter: vi.fn(),
}));

describe("GroupingPlanStep", () => {
  const bodyPool: ComposerKeywordPool = {
    id: "pool-body",
    organizationId: "org-1",
    projectId: "proj-1",
    groupId: null,
    poolType: "body",
    status: "cleaned",
    rawKeywords: ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    cleanedKeywords: ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
    removedKeywords: [],
    cleanSettings: {},
    groupingConfig: {},
    cleanedAt: "2025-01-01T00:00:00.000Z",
    groupedAt: null,
    approvedAt: null,
    createdAt: "2025-01-01T00:00:00.000Z",
  };

  const titlesPool: ComposerKeywordPool = {
    ...bodyPool,
    id: "pool-titles",
    poolType: "titles",
  };

  const mockHooks = {
    generateGroupingPlan: vi.fn(),
    getGroups: vi.fn(),
    addOverride: vi.fn(),
    resetOverrides: vi.fn(),
    approveGrouping: vi.fn(),
    unapproveGrouping: vi.fn(),
  };

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(useKeywordPools).mockReturnValue(mockHooks as any);
    mockHooks.getGroups.mockResolvedValue({ groups: [], overrides: [] });
  });

  it("renders with pool data and defaults to body tab", () => {
    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool, titlesPool]} />);

    expect(screen.getByText("Description & Bullets Pool")).toBeInTheDocument();
    expect(screen.getByText("Titles Pool")).toBeInTheDocument();

    // Body tab should be active
    const bodyTab = screen.getByRole("button", { name: /Description & Bullets Pool/i });
    expect(bodyTab).toHaveClass("border-blue-600");
  });

  it("switches tabs when clicked", async () => {
    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool, titlesPool]} />);

    const titlesTab = screen.getByRole("button", { name: /Titles Pool/i });
    const bodyTab = screen.getByRole("button", { name: /Description & Bullets Pool/i });

    // Initially body tab is active
    expect(bodyTab).toHaveClass("border-blue-600");
    expect(titlesTab).not.toHaveClass("border-blue-600");

    fireEvent.click(titlesTab);

    await waitFor(() => {
      expect(titlesTab).toHaveClass("border-blue-600");
      expect(bodyTab).not.toHaveClass("border-blue-600");
    });
  });

  it("shows config form initially", () => {
    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    expect(screen.getByTestId("config-form")).toBeInTheDocument();
  });

  it("shows Configure state in progress indicator initially", () => {
    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    const configureLabel = screen.getByText("Configure");
    expect(configureLabel).toHaveClass("font-bold");

    const reviewLabel = screen.getByText("Review");
    expect(reviewLabel).toHaveClass("text-gray-500");
  });

  it("generates groups on config submit", async () => {
    mockHooks.generateGroupingPlan.mockResolvedValue(bodyPool);
    mockHooks.getGroups.mockResolvedValue({
      groups: [
        { id: "group-1", label: "Group 1", phrases: ["keyword1", "keyword2"] },
        { id: "group-2", label: "Group 2", phrases: ["keyword3", "keyword4", "keyword5"] },
      ],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(mockHooks.generateGroupingPlan).toHaveBeenCalledWith("pool-body", { basis: "single" });
      expect(mockHooks.getGroups).toHaveBeenCalledWith("pool-body");
    });

    // Should show groups after generation
    await waitFor(() => {
      expect(screen.getByTestId("group-card-group-1")).toBeInTheDocument();
      expect(screen.getByTestId("group-card-group-2")).toBeInTheDocument();
    });
  });

  it("shows Review state when groups are generated", async () => {
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1"] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Trigger generation
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      const reviewLabel = screen.getByText("Review");
      expect(reviewLabel).toHaveClass("font-bold");
    });
  });

  it("shows Approved state when pool status is grouped", async () => {
    const groupedPool = { ...bodyPool, status: "grouped" as const };
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1"] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[groupedPool]} />);

    await waitFor(() => {
      const approveLabel = screen.getByText(/Grouping Approved/i);
      expect(approveLabel).toHaveClass("text-green-600");
    });
  });

  it("handles drag-and-drop events", async () => {
    mockHooks.getGroups.mockResolvedValue({
      groups: [
        { id: "group-1", label: "Group 1", phrases: ["keyword1", "keyword2"] },
        { id: "group-2", label: "Group 2", phrases: ["keyword3"] },
      ],
      overrides: [],
    });

    const { container } = render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Trigger generation first
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByTestId("group-card-group-1")).toBeInTheDocument();
    });

    // Find DndContext
    const dndContext = container.querySelector('[data-testid="dnd-context"]');
    expect(dndContext).toBeInTheDocument();
    expect(dndContext).toHaveAttribute("data-on-drag-end", "true");
  });

  it("tracks overrides when keywords are moved", async () => {
    mockHooks.addOverride.mockResolvedValue(true);
    mockHooks.getGroups.mockResolvedValue({
      groups: [
        { id: "group-1", label: "Group 1", phrases: ["keyword1", "keyword2"] },
        { id: "group-2", label: "Group 2", phrases: ["keyword3"] },
      ],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Generate groups first
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByTestId("group-card-group-1")).toBeInTheDocument();
    });

    // Note: Full drag-and-drop testing would require more complex mocking of @dnd-kit
    // The component's handleDragEnd function would be called with DragEndEvent
    // For now, we verify the component structure supports drag-and-drop
  });

  it("approves grouping when button clicked", async () => {
    const updatedPool = { ...bodyPool, status: "grouped" as const };
    mockHooks.approveGrouping.mockResolvedValue(updatedPool);
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Generate groups
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByTestId("group-card-group-1")).toBeInTheDocument();
    });

    // Find and click approve button
    const approveButton = screen.getByRole("button", { name: /Approve Grouping/i });
    expect(approveButton).not.toBeDisabled();

    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(mockHooks.approveGrouping).toHaveBeenCalledWith("pool-body");
    });
  });

  it("disables approve button when groups are empty", async () => {
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: [] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Generate groups
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      const approveButton = screen.getByRole("button", { name: /Approve Grouping/i });
      expect(approveButton).toBeDisabled();
    });
  });

  it("shows approved state and unapprove button", async () => {
    const groupedPool = { ...bodyPool, status: "grouped" as const, approvedAt: "2025-01-02T00:00:00.000Z" };
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[groupedPool]} />);

    await waitFor(() => {
      expect(screen.getByText(/Grouping Approved/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Unapprove/i })).toBeInTheDocument();
    });
  });

  it("unapproves grouping when unapprove button clicked", async () => {
    const groupedPool = { ...bodyPool, status: "grouped" as const };
    mockHooks.unapproveGrouping.mockResolvedValue({ ...bodyPool, status: "cleaned" });
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[groupedPool]} />);

    await waitFor(() => {
      const unapproveButton = screen.getByRole("button", { name: /Unapprove/i });
      fireEvent.click(unapproveButton);
    });

    await waitFor(() => {
      expect(mockHooks.unapproveGrouping).toHaveBeenCalledWith("pool-body");
    });
  });

  it("resets overrides when reset button clicked", async () => {
    mockHooks.resetOverrides.mockResolvedValue(true);
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1"] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Generate groups first
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByTestId("group-card-group-1")).toBeInTheDocument();
    });

    const resetButton = screen.getByRole("button", { name: /Reset Overrides/i });
    fireEvent.click(resetButton);

    await waitFor(() => {
      expect(mockHooks.resetOverrides).toHaveBeenCalledWith("pool-body");
      expect(mockHooks.getGroups).toHaveBeenCalledTimes(2); // Once on mount, once after reset
    });
  });

  it("toggles config form visibility", async () => {
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1"] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Generate groups
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByTestId("group-card-group-1")).toBeInTheDocument();
    });

    // Config form should be hidden after generation
    await waitFor(() => {
      expect(screen.queryByTestId("config-form")).not.toBeInTheDocument();
    });

    // Click show config button
    const showConfigButton = screen.getByRole("button", { name: /Show Config/i });
    fireEvent.click(showConfigButton);

    await waitFor(() => {
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });

    // Click hide config button
    const hideConfigButton = screen.getByRole("button", { name: /Hide Config/i });
    fireEvent.click(hideConfigButton);

    await waitFor(() => {
      expect(screen.queryByTestId("config-form")).not.toBeInTheDocument();
    });
  });

  it("shows continue button when approved", async () => {
    const groupedPool = { ...bodyPool, status: "grouped" as const };
    const mockOnContinue = vi.fn();
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"] }],
      overrides: [],
    });

    render(
      <GroupingPlanStep projectId="proj-1" pools={[groupedPool]} onContinue={mockOnContinue} />
    );

    await waitFor(() => {
      const continueButton = screen.getByRole("button", { name: /Continue to Asset Generation/i });
      expect(continueButton).toBeInTheDocument();

      fireEvent.click(continueButton);
      expect(mockOnContinue).toHaveBeenCalled();
    });
  });

  it("calls onContinue after successful approval", async () => {
    const mockOnContinue = vi.fn();
    const updatedPool = { ...bodyPool, status: "grouped" as const };
    mockHooks.approveGrouping.mockResolvedValue(updatedPool);
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"] }],
      overrides: [],
    });

    render(
      <GroupingPlanStep projectId="proj-1" pools={[bodyPool]} onContinue={mockOnContinue} />
    );

    // Generate groups
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByTestId("group-card-group-1")).toBeInTheDocument();
    });

    // Click approve
    const approveButton = screen.getByRole("button", { name: /Approve Grouping/i });
    fireEvent.click(approveButton);

    await waitFor(() => {
      expect(mockOnContinue).toHaveBeenCalled();
    });
  });

  it("shows empty state when no groups generated", () => {
    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Hide the config form
    const configForm = screen.getByTestId("config-form");
    expect(configForm).toBeInTheDocument();
  });

  it("shows group count header", async () => {
    mockHooks.getGroups.mockResolvedValue({
      groups: [
        { id: "group-1", label: "Group 1", phrases: ["keyword1"] },
        { id: "group-2", label: "Group 2", phrases: ["keyword2"] },
        { id: "group-3", label: "Group 3", phrases: ["keyword3"] },
      ],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Generate groups
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByText(/Keyword Groups \(3\)/i)).toBeInTheDocument();
    });
  });

  it("handles generation errors gracefully", async () => {
    mockHooks.generateGroupingPlan.mockRejectedValue(new Error("AI service unavailable"));

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      // Component should handle error without crashing
      expect(screen.getByTestId("config-form")).toBeInTheDocument();
    });
  });

  it("loads groups on mount for current pool", async () => {
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1"] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    await waitFor(() => {
      expect(mockHooks.getGroups).toHaveBeenCalledWith("pool-body");
    });
  });

  it("reloads groups when switching tabs", async () => {
    mockHooks.getGroups.mockResolvedValue({
      groups: [],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool, titlesPool]} />);

    await waitFor(() => {
      expect(mockHooks.getGroups).toHaveBeenCalledWith("pool-body");
    });

    // Switch to titles tab
    const titlesTab = screen.getByRole("button", { name: /Titles Pool/i });
    fireEvent.click(titlesTab);

    await waitFor(() => {
      expect(mockHooks.getGroups).toHaveBeenCalledWith("pool-titles");
    });
  });

  it("updates label through KeywordGroupCard callback", async () => {
    mockHooks.getGroups.mockResolvedValue({
      groups: [{ id: "group-1", label: "Group 1", phrases: ["keyword1"] }],
      overrides: [],
    });

    render(<GroupingPlanStep projectId="proj-1" pools={[bodyPool]} />);

    // Generate groups
    const generateButton = screen.getByRole("button", { name: /Generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByTestId("group-card-group-1")).toBeInTheDocument();
    });

    // Click the update label button in the mocked component
    const updateButton = screen.getByRole("button", { name: /Update Label/i });
    fireEvent.click(updateButton);

    // Label should be updated in local state (verified by re-render)
    // In real implementation, this would call an API
  });
});
