/**
 * @vitest-environment jsdom
 */
/// <reference types="vitest/globals" />
import "@testing-library/jest-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GroupingConfigForm } from "./GroupingConfigForm";

describe("GroupingConfigForm", () => {
  const mockOnGenerate = vi.fn();

  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders with default single basis option selected", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByLabelText(/Grouping Strategy/i);
    expect(basisSelect).toHaveValue("single");
    expect(screen.getByRole("button", { name: /Generate Grouping Plan/i })).toBeInTheDocument();
  });

  it("shows attribute name input when attribute basis is selected", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByLabelText(/Grouping Strategy/i);
    fireEvent.change(basisSelect, { target: { value: "attribute" } });

    const attributeInput = screen.getByPlaceholderText(/e.g., color, size, style/i);
    expect(attributeInput).toBeInTheDocument();
    expect(attributeInput).toHaveAttribute("required");
  });

  it("shows group count and phrases per group inputs when custom basis is selected", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByLabelText(/Grouping Strategy/i);
    fireEvent.change(basisSelect, { target: { value: "custom" } });

    const groupCountInput = screen.getByLabelText(/Number of Groups/i);
    const phrasesPerGroupInput = screen.getByLabelText(/Keywords Per Group/i);

    expect(groupCountInput).toBeInTheDocument();
    expect(phrasesPerGroupInput).toBeInTheDocument();
    expect(groupCountInput).toHaveValue(3);
    expect(phrasesPerGroupInput).toHaveValue(10);
  });

  it("submits form with single basis configuration", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const submitButton = screen.getByRole("button", { name: /Generate Grouping Plan/i });
    fireEvent.click(submitButton);

    expect(mockOnGenerate).toHaveBeenCalledWith({
      basis: "single",
    });
  });

  it("submits form with per_sku basis configuration", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });
    fireEvent.change(basisSelect, { target: { value: "per_sku" } });

    const submitButton = screen.getByRole("button", { name: /Generate Grouping Plan/i });
    fireEvent.click(submitButton);

    expect(mockOnGenerate).toHaveBeenCalledWith({
      basis: "per_sku",
    });
  });

  it("submits form with attribute basis and attribute name", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });
    fireEvent.change(basisSelect, { target: { value: "attribute" } });

    const attributeInput = screen.getByPlaceholderText(/e.g., color, size, style/i);
    fireEvent.change(attributeInput, { target: { value: "color" } });

    const submitButton = screen.getByRole("button", { name: /Generate Grouping Plan/i });
    fireEvent.click(submitButton);

    expect(mockOnGenerate).toHaveBeenCalledWith({
      basis: "attribute",
      attributeName: "color",
    });
  });

  it("submits form with custom basis and group settings", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });
    fireEvent.change(basisSelect, { target: { value: "custom" } });

    const groupCountInput = screen.getByLabelText(/Number of Groups/i);
    const phrasesPerGroupInput = screen.getByLabelText(/Keywords Per Group/i);

    fireEvent.change(groupCountInput, { target: { value: "5" } });
    fireEvent.change(phrasesPerGroupInput, { target: { value: "15" } });

    const submitButton = screen.getByRole("button", { name: /Generate Grouping Plan/i });
    fireEvent.click(submitButton);

    expect(mockOnGenerate).toHaveBeenCalledWith({
      basis: "custom",
      groupCount: 5,
      phrasesPerGroup: 15,
    });
  });

  it("disables form inputs when isGenerating is true", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} isGenerating={true} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });
    const submitButton = screen.getByRole("button", { name: /Generating Groups.../i });

    expect(basisSelect).toBeDisabled();
    expect(submitButton).toBeDisabled();
  });

  it("shows generating state text on submit button", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} isGenerating={true} />);

    expect(screen.getByRole("button", { name: /Generating Groups.../i })).toBeInTheDocument();
  });

  it("validates attribute name is required when attribute basis selected", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });
    fireEvent.change(basisSelect, { target: { value: "attribute" } });

    const attributeInput = screen.getByPlaceholderText(/e.g., color, size, style/i);
    expect(attributeInput).toHaveAttribute("required");
  });

  it("handles min/max constraints for custom group count", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });
    fireEvent.change(basisSelect, { target: { value: "custom" } });

    const groupCountInput = screen.getByLabelText(/Number of Groups/i);
    expect(groupCountInput).toHaveAttribute("min", "1");
    expect(groupCountInput).toHaveAttribute("max", "20");
  });

  it("handles min/max constraints for phrases per group", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });
    fireEvent.change(basisSelect, { target: { value: "custom" } });

    const phrasesPerGroupInput = screen.getByLabelText(/Keywords Per Group/i);
    expect(phrasesPerGroupInput).toHaveAttribute("min", "1");
    expect(phrasesPerGroupInput).toHaveAttribute("max", "100");
  });

  it("handles invalid number input gracefully", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });
    fireEvent.change(basisSelect, { target: { value: "custom" } });

    const groupCountInput = screen.getByLabelText(/Number of Groups/i);
    fireEvent.change(groupCountInput, { target: { value: "" } });

    const submitButton = screen.getByRole("button", { name: /Generate Grouping Plan/i });
    fireEvent.click(submitButton);

    // Should fall back to default value of 3
    expect(mockOnGenerate).toHaveBeenCalledWith({
      basis: "custom",
      groupCount: 3,
      phrasesPerGroup: 10,
    });
  });

  it("does not include attributeName for non-attribute basis", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });

    // Set to attribute first
    fireEvent.change(basisSelect, { target: { value: "attribute" } });
    const attributeInput = screen.getByPlaceholderText(/e.g., color, size, style/i);
    fireEvent.change(attributeInput, { target: { value: "color" } });

    // Change back to single
    fireEvent.change(basisSelect, { target: { value: "single" } });

    const submitButton = screen.getByRole("button", { name: /Generate Grouping Plan/i });
    fireEvent.click(submitButton);

    // Should not include attributeName
    expect(mockOnGenerate).toHaveBeenCalledWith({
      basis: "single",
    });
  });

  it("does not include groupCount/phrasesPerGroup for non-custom basis", () => {
    render(<GroupingConfigForm onGenerate={mockOnGenerate} />);

    const basisSelect = screen.getByRole("combobox", { name: /Grouping Strategy/i });

    // Set to custom first
    fireEvent.change(basisSelect, { target: { value: "custom" } });
    const groupCountInput = screen.getByLabelText(/Number of Groups/i);
    fireEvent.change(groupCountInput, { target: { value: "7" } });

    // Change back to per_sku
    fireEvent.change(basisSelect, { target: { value: "per_sku" } });

    const submitButton = screen.getByRole("button", { name: /Generate Grouping Plan/i });
    fireEvent.click(submitButton);

    // Should not include groupCount or phrasesPerGroup
    expect(mockOnGenerate).toHaveBeenCalledWith({
      basis: "per_sku",
    });
  });

  it("disables attribute input when isGenerating is true", () => {
    const { rerender } = render(<GroupingConfigForm onGenerate={mockOnGenerate} isGenerating={false} />);

    fireEvent.change(screen.getByRole("combobox", { name: /Grouping Strategy/i }), {
      target: { value: "attribute" },
    });
    expect(screen.getByPlaceholderText(/e.g., color, size, style/i)).not.toBeDisabled();

    rerender(<GroupingConfigForm onGenerate={mockOnGenerate} isGenerating={true} />);

    expect(screen.getByPlaceholderText(/e.g., color, size, style/i)).toBeDisabled();
  });

  it("disables custom inputs when isGenerating is true", () => {
    const { rerender } = render(<GroupingConfigForm onGenerate={mockOnGenerate} isGenerating={false} />);

    fireEvent.change(screen.getByRole("combobox", { name: /Grouping Strategy/i }), {
      target: { value: "custom" },
    });

    expect(screen.getByLabelText(/Number of Groups/i)).not.toBeDisabled();
    expect(screen.getByLabelText(/Keywords Per Group/i)).not.toBeDisabled();

    rerender(<GroupingConfigForm onGenerate={mockOnGenerate} isGenerating={true} />);

    expect(screen.getByLabelText(/Number of Groups/i)).toBeDisabled();
    expect(screen.getByLabelText(/Keywords Per Group/i)).toBeDisabled();
  });
});
