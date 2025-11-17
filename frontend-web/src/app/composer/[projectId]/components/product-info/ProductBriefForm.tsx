"use client";

import type { ProductBrief } from "../../../../../../../lib/composer/types";

interface ProductBriefFormProps {
  productBrief: ProductBrief;
  suppliedInfoNotes: string;
  onProductBriefChange: (brief: ProductBrief) => void;
  onSuppliedInfoChange: (notes: string) => void;
}

const BRIEF_FIELDS: Array<{
  key: keyof ProductBrief;
  label: string;
  placeholder: string;
}> = [
  { key: "targetAudience", label: "Target Audience", placeholder: "Parents looking for eco toys…" },
  { key: "useCases", label: "Use Cases", placeholder: "Daily stroller walks, bedtime routine…" },
  { key: "differentiators", label: "Differentiators", placeholder: "100% organic, award-winning design…" },
  { key: "safetyNotes", label: "Safety Notes", placeholder: "No small parts, BPA-free, lab tested…" },
  { key: "certifications", label: "Certifications / Claims", placeholder: "USDA Organic, CPSIA compliant…" },
];

export const ProductBriefForm = ({
  productBrief,
  suppliedInfoNotes,
  onProductBriefChange,
  onSuppliedInfoChange,
}: ProductBriefFormProps) => {
  const updateField = (key: keyof ProductBrief, value: string) => {
    onProductBriefChange({
      ...productBrief,
      [key]: value,
    });
  };

  return (
    <section className="rounded-2xl border border-[#cbd5f5] bg-white/90 p-6 shadow-inner">
      <header className="mb-4 flex flex-col gap-1">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">
          Product Brief
        </p>
        <h2 className="text-2xl font-semibold text-[#0f172a]">Positioning</h2>
        <p className="text-sm text-[#475569]">Five prompts to capture the story before keywords.</p>
      </header>

      <div className="space-y-4">
        {BRIEF_FIELDS.map((field) => (
          <label key={field.key as string} className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-[#475569]">
              {field.label}
            </span>
            <textarea
              className="mt-1 w-full rounded-xl border border-[#cbd5f5] bg-white px-4 py-3 text-sm text-[#0f172a] shadow-sm focus:border-[#0a6fd6] focus:outline-none"
              rows={3}
              value={(productBrief[field.key] as string | undefined) ?? ""}
              placeholder={field.placeholder}
              onChange={(event) => updateField(field.key, event.target.value)}
            />
          </label>
        ))}

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-[#475569]">
            Additional Client Notes
          </span>
          <textarea
            className="mt-1 w-full rounded-xl border border-[#cbd5f5] bg-white px-4 py-3 text-sm text-[#0f172a] shadow-sm focus:border-[#0a6fd6] focus:outline-none"
            rows={4}
            value={suppliedInfoNotes}
            placeholder="Paste any extra client input, context docs, or reminders."
            onChange={(event) => onSuppliedInfoChange(event.target.value)}
          />
        </label>
      </div>
    </section>
  );
};
