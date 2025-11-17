"use client";

import { useState } from "react";

interface BrandGuidelinesFormProps {
  brandTone: string;
  whatNotToSay: string[];
  onChange: (changes: { brandTone?: string; whatNotToSay?: string[] }) => void;
}

export const BrandGuidelinesForm = ({ brandTone, whatNotToSay, onChange }: BrandGuidelinesFormProps) => {
  const [newTerm, setNewTerm] = useState("");

  const addTerm = () => {
    const trimmed = newTerm.trim();
    if (!trimmed) return;
    const next = Array.from(new Set([...whatNotToSay, trimmed]));
    onChange({ whatNotToSay: next });
    setNewTerm("");
  };

  const removeTerm = (term: string) => {
    onChange({ whatNotToSay: whatNotToSay.filter((entry) => entry !== term) });
  };

  return (
    <section className="rounded-2xl border border-[#cbd5f5] bg-white/90 p-6 shadow-inner">
      <header className="mb-4 flex flex-col gap-1">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">
          Brand Guidelines
        </p>
        <h2 className="text-2xl font-semibold text-[#0f172a]">Tone & Guardrails</h2>
        <p className="text-sm text-[#475569]">
          Capture the nuance for this client so downstream copy stays compliant.
        </p>
      </header>

      <div className="space-y-4">
        <label className="block">
          <span className="text-xs font-semibold uppercase tracking-wide text-[#475569]">Brand Tone</span>
          <textarea
            className="mt-1 w-full rounded-xl border border-[#cbd5f5] bg-white px-4 py-3 text-sm text-[#0f172a] shadow-sm focus:border-[#0a6fd6] focus:outline-none"
            rows={3}
            value={brandTone}
            placeholder="Friendly, confident, avoid buzzwords…"
            onChange={(event) => onChange({ brandTone: event.target.value })}
          />
        </label>

        <div>
          <span className="text-xs font-semibold uppercase tracking-wide text-[#475569]">What NOT to say</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {whatNotToSay.map((term) => (
              <span
                key={term}
                className="flex items-center gap-2 rounded-full bg-[#fee2e2] px-3 py-1 text-xs font-semibold text-[#b91c1c]"
              >
                {term}
                <button type="button" className="text-[#b91c1c]" onClick={() => removeTerm(term)}>
                  ×
                </button>
              </span>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <input
              type="text"
              className="flex-1 rounded-xl border border-[#cbd5f5] bg-white px-4 py-2 text-sm text-[#0f172a] shadow-sm focus:border-[#0a6fd6] focus:outline-none"
              value={newTerm}
              onChange={(event) => setNewTerm(event.target.value)}
              placeholder="Add a banned phrase"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addTerm();
                }
              }}
            />
            <button
              type="button"
              className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-xs font-semibold text-white shadow-sm disabled:opacity-40"
              onClick={addTerm}
            >
              Add
            </button>
          </div>
        </div>
      </div>
    </section>
  );
};
