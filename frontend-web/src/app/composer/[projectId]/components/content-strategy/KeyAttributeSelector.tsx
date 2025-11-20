"use client";

import type { HighlightAttributePreference, HighlightSurface } from "@agency/lib/composer/types";
import type { AttributeSummary } from "@/lib/composer/productInfo/inferAttributes";

const SURFACES: { key: HighlightSurface; label: string }[] = [
  { key: "title", label: "Title" },
  { key: "bullets", label: "Bullets" },
  { key: "description", label: "Description" },
  { key: "backend_keywords", label: "Backend Keywords" },
];

const EMPTY_SURFACES: Record<HighlightSurface, boolean> = {
  title: false,
  bullets: false,
  description: false,
  backend_keywords: false,
};

interface KeyAttributeSelectorProps {
  attributes: AttributeSummary[];
  preferences: HighlightAttributePreference[];
  onChange: (next: HighlightAttributePreference[]) => void;
}

const findPreference = (
  preferences: HighlightAttributePreference[],
  key: string,
) => preferences.find((preference) => preference.key === key);

export const KeyAttributeSelector = ({
  attributes,
  preferences,
  onChange,
}: KeyAttributeSelectorProps) => {
  const handleToggle = (attributeKey: string, surface: HighlightSurface, checked: boolean) => {
    const existing = findPreference(preferences, attributeKey);
    const nextSurfaces = {
      ...EMPTY_SURFACES,
      ...(existing?.surfaces ?? {}),
      [surface]: checked,
    };
    const hasAny = Object.values(nextSurfaces).some(Boolean);
    let nextPreferences: HighlightAttributePreference[];
    if (hasAny) {
      const updatedPreference: HighlightAttributePreference = {
        key: attributeKey,
        surfaces: nextSurfaces,
      };
      if (existing) {
        nextPreferences = preferences.map((preference) =>
          preference.key === attributeKey ? updatedPreference : preference,
        );
      } else {
        nextPreferences = [...preferences, updatedPreference];
      }
    } else {
      nextPreferences = preferences.filter((preference) => preference.key !== attributeKey);
    }
    onChange(nextPreferences);
  };

  return (
    <section className="rounded-2xl border border-[#e2e8f0] bg-white p-4">
      <h3 className="text-sm font-semibold text-[#0f172a]">Key attribute highlights</h3>
      <p className="mt-1 text-sm text-[#475569]">
        Choose where each attribute must be mentioned. Leave boxes unchecked if an attribute should
        only appear when it’s naturally relevant.
      </p>

      {attributes.length === 0 ? (
        <div className="mt-3 rounded-lg border border-dashed border-[#cbd5e1] bg-[#f8fafc] px-4 py-3 text-sm text-[#64748b]">
          No attributes detected yet. Add attribute columns in the Product Info step to enable this.
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-[#e2e8f0] text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-[#94a3b8]">
                <th className="py-2 pr-4">Attribute</th>
                {SURFACES.map((surface) => (
                  <th key={surface.key} className="py-2 px-4 text-center">
                    {surface.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#f1f5f9]">
              {attributes.map((attribute) => {
                const preference = findPreference(preferences, attribute.key);
                return (
                  <tr key={attribute.key}>
                    <td className="py-3 pr-4 font-medium text-[#0f172a]">
                      <div>{attribute.key}</div>
                      <div className="text-xs text-[#475569]">
                        {attribute.filledCount}/{attribute.totalCount} SKUs
                      </div>
                    </td>
                    {SURFACES.map((surface) => (
                      <td key={surface.key} className="py-3 px-4 text-center">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-[#cbd5e1] text-[#0a6fd6] focus:ring-[#0a6fd6]"
                          checked={Boolean(preference?.surfaces[surface.key])}
                          onChange={(event) =>
                            handleToggle(attribute.key, surface.key, event.target.checked)
                          }
                        />
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};
