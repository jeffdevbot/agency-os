"use client";

import type { ProductInfoFormErrors, ProductInfoFormState } from "@/lib/composer/productInfo/types";

interface ProjectMetaFormProps {
  value: ProductInfoFormState;
  errors: ProductInfoFormErrors;
  onChange: (changes: Partial<ProductInfoFormState>) => void;
  marketplaceOptions: string[];
}

export const ProjectMetaForm = ({ value, errors, onChange, marketplaceOptions }: ProjectMetaFormProps) => {
  const toggleMarketplace = (marketplace: string) => {
    const exists = value.marketplaces.includes(marketplace);
    const next = exists
      ? value.marketplaces.filter((entry) => entry !== marketplace)
      : [...value.marketplaces, marketplace];
    onChange({ marketplaces: next });
  };

  return (
    <section className="rounded-2xl border border-[#cbd5f5] bg-white/90 p-6 shadow-inner">
      <header className="mb-4 flex flex-col gap-1">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">
          Project Meta
        </p>
        <h2 className="text-2xl font-semibold text-[#0f172a]">Basics</h2>
        <p className="text-sm text-[#475569]">Client + marketplace context drives every downstream step.</p>
      </header>

      <div className="space-y-4">
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-[#475569]">Project Name</span>
          <input
            type="text"
            className="mt-1 w-full rounded-xl border border-[#cbd5f5] bg-white px-4 py-2 text-sm text-[#0f172a] shadow-sm focus:border-[#0a6fd6] focus:outline-none"
            value={value.projectName}
            onChange={(event) => onChange({ projectName: event.target.value })}
            placeholder="ex. Q4 Holiday Bundles"
          />
          {errors.projectName && <p className="mt-1 text-xs text-[#b91c1c]">{errors.projectName}</p>}
        </label>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-[#475569]">Client / Brand</span>
          <input
            type="text"
            className="mt-1 w-full rounded-xl border border-[#cbd5f5] bg-white px-4 py-2 text-sm text-[#0f172a] shadow-sm focus:border-[#0a6fd6] focus:outline-none"
            value={value.clientName}
            onChange={(event) => onChange({ clientName: event.target.value })}
            placeholder="Brand name"
          />
          {errors.clientName && <p className="mt-1 text-xs text-[#b91c1c]">{errors.clientName}</p>}
        </label>

        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-[#475569]">Marketplaces</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {marketplaceOptions.map((marketplace) => {
              const isSelected = value.marketplaces.includes(marketplace);
              return (
                <button
                  key={marketplace}
                  type="button"
                  onClick={() => toggleMarketplace(marketplace)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold shadow-sm transition ${
                    isSelected ? "bg-[#0a6fd6] text-white" : "bg-[#eef2ff] text-[#475569]"
                  }`}
                >
                  {marketplace}
                </button>
              );
            })}
          </div>
          {errors.marketplaces && <p className="mt-2 text-xs text-[#b91c1c]">{errors.marketplaces}</p>}
        </div>

        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-[#475569]">Category</span>
          <input
            type="text"
            className="mt-1 w-full rounded-xl border border-[#cbd5f5] bg-white px-4 py-2 text-sm text-[#0f172a] shadow-sm focus:border-[#0a6fd6] focus:outline-none"
            value={value.category}
            onChange={(event) => onChange({ category: event.target.value })}
            placeholder="Optional — e.g. Toys & Games"
          />
        </label>
      </div>
    </section>
  );
};
