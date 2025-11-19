import { describe, it, expect } from "vitest";
import { validateProductInfoForm } from "./validateProductInfoForm";
import type { ComposerProject, ComposerSkuVariant } from "@agency/lib/composer/types";

const createValidProject = (overrides?: Partial<ComposerProject>): ComposerProject => ({
  id: "proj-1",
  organizationId: "org-1",
  projectName: "Test Project",
  clientName: "Test Client",
  marketplaces: ["US"],
  brandTone: null,
  whatNotToSay: [],
  productBrief: "",
  suppliedInfoNotes: null,
  faq: [],
  status: "draft",
  activeStep: "product_info",
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  lastSavedAt: null,
  ...overrides,
});

const createValidVariant = (overrides?: Partial<ComposerSkuVariant>): ComposerSkuVariant => ({
  id: "var-1",
  projectId: "proj-1",
  sku: "SKU-001",
  asin: null,
  parentSku: null,
  attributes: {},
  notes: null,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  ...overrides,
});

describe("validateProductInfoForm", () => {
  describe("valid form", () => {
    it("returns isValid true when all requirements met", () => {
      const project = createValidProject();
      const variants = [createValidVariant()];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(true);
      expect(result.errors).toEqual({});
    });

    it("accepts multiple marketplaces", () => {
      const project = createValidProject({ marketplaces: ["US", "CA", "MX"] });
      const variants = [createValidVariant()];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(true);
    });

    it("accepts multiple variants", () => {
      const project = createValidProject();
      const variants = [
        createValidVariant({ id: "1", sku: "SKU-001" }),
        createValidVariant({ id: "2", sku: "SKU-002" }),
      ];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(true);
    });
  });

  describe("project validation", () => {
    it("returns error when project is null", () => {
      const result = validateProductInfoForm(null, []);
      expect(result.isValid).toBe(false);
      expect(result.errors.projectName).toBe("Project data not loaded");
    });

    it("returns error when projectName is empty", () => {
      const project = createValidProject({ projectName: "" });
      const variants = [createValidVariant()];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(false);
      expect(result.errors.projectName).toBe("Project name is required");
    });

    it("returns error when projectName is whitespace only", () => {
      const project = createValidProject({ projectName: "   " });
      const variants = [createValidVariant()];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(false);
      expect(result.errors.projectName).toBe("Project name is required");
    });

    it("returns error when clientName is empty", () => {
      const project = createValidProject({ clientName: "" });
      const variants = [createValidVariant()];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(false);
      expect(result.errors.clientName).toBe("Client name is required");
    });

    it("returns error when clientName is whitespace only", () => {
      const project = createValidProject({ clientName: "   " });
      const variants = [createValidVariant()];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(false);
      expect(result.errors.clientName).toBe("Client name is required");
    });
  });

  describe("marketplace validation", () => {
    it("returns error when marketplaces is empty array", () => {
      const project = createValidProject({ marketplaces: [] });
      const variants = [createValidVariant()];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(false);
      expect(result.errors.marketplaces).toBe("At least one marketplace is required");
    });

    it("returns error when marketplaces is undefined", () => {
      const project = createValidProject({ marketplaces: undefined as unknown as string[] });
      const variants = [createValidVariant()];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(false);
      expect(result.errors.marketplaces).toBe("At least one marketplace is required");
    });
  });

  describe("variant validation", () => {
    it("returns error when no variants provided", () => {
      const project = createValidProject();
      const result = validateProductInfoForm(project, []);
      expect(result.isValid).toBe(false);
      expect(result.errors.variants).toBe("At least one SKU is required");
    });

    it("returns error when all variants have empty SKUs", () => {
      const project = createValidProject();
      const variants = [
        createValidVariant({ sku: "" }),
        createValidVariant({ id: "2", sku: "   " }),
      ];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(false);
      expect(result.errors.variants).toBe("At least one SKU is required");
    });

    it("passes when at least one variant has valid SKU", () => {
      const project = createValidProject();
      const variants = [
        createValidVariant({ sku: "" }),
        createValidVariant({ id: "2", sku: "SKU-001" }),
      ];
      const result = validateProductInfoForm(project, variants);
      // Still has row-level errors but variants check passes
      expect(result.errors.variants).toBeUndefined();
    });
  });

  describe("row-level errors", () => {
    it("returns row errors for variants with empty SKUs", () => {
      const project = createValidProject();
      const variants = [
        createValidVariant({ sku: "" }),
        createValidVariant({ id: "2", sku: "SKU-001" }),
        createValidVariant({ id: "3", sku: "   " }),
      ];
      const result = validateProductInfoForm(project, variants);
      expect(result.errors.rows).toHaveLength(2);
      expect(result.errors.rows).toContainEqual({ index: 0, sku: "SKU is required" });
      expect(result.errors.rows).toContainEqual({ index: 2, sku: "SKU is required" });
    });

    it("does not include row errors when all SKUs are valid", () => {
      const project = createValidProject();
      const variants = [
        createValidVariant({ sku: "SKU-001" }),
        createValidVariant({ id: "2", sku: "SKU-002" }),
      ];
      const result = validateProductInfoForm(project, variants);
      expect(result.errors.rows).toBeUndefined();
    });
  });

  describe("multiple errors", () => {
    it("returns all applicable errors at once", () => {
      const project = createValidProject({
        projectName: "",
        clientName: "",
        marketplaces: [],
      });
      const variants: ComposerSkuVariant[] = [];
      const result = validateProductInfoForm(project, variants);
      expect(result.isValid).toBe(false);
      expect(result.errors.projectName).toBeDefined();
      expect(result.errors.clientName).toBeDefined();
      expect(result.errors.marketplaces).toBeDefined();
      expect(result.errors.variants).toBeDefined();
    });
  });
});
