"use client";

import { useCallback } from "react";
import type { FaqFormItem } from "@/lib/composer/productInfo/types";

interface FaqRepeaterProps {
  faq: FaqFormItem[];
  onChange: (nextFaq: FaqFormItem[]) => void;
}

const createClientId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `faq-${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

export const FaqRepeater = ({ faq, onChange }: FaqRepeaterProps) => {
  const updateItem = useCallback(
    (clientId: string, field: keyof FaqFormItem, value: string) => {
      onChange(
        faq.map((item) =>
          item.clientId === clientId
            ? {
                ...item,
                [field]: value,
              }
            : item,
        ),
      );
    },
    [faq, onChange],
  );

  const addFaq = () => {
    onChange([...faq, { clientId: createClientId(), question: "", answer: "" }]);
  };

  const removeFaq = (clientId: string) => {
    onChange(faq.filter((item) => item.clientId !== clientId));
  };

  return (
    <section className="rounded-2xl border border-[#cbd5f5] bg-white/90 p-6 shadow-inner">
      <header className="mb-4 flex flex-col gap-1">
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#94a3b8]">FAQ</p>
        <h2 className="text-2xl font-semibold text-[#0f172a]">Anticipated Questions</h2>
        <p className="text-sm text-[#475569]">
          Capture quick Q&A that VAs or clients reference often.
        </p>
      </header>

      <div className="space-y-4">
        {faq.length === 0 && <p className="text-sm text-[#94a3b8]">No FAQ entries yet.</p>}
        {faq.map((item, index) => (
          <div key={item.clientId} className="rounded-xl border border-[#e2e8f0] p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-[#475569]">
                Question {index + 1}
              </span>
              <button
                type="button"
                className="text-xs font-semibold text-[#b91c1c]"
                onClick={() => removeFaq(item.clientId)}
              >
                Remove
              </button>
            </div>
            <input
              type="text"
              className="mt-2 w-full rounded-xl border border-[#cbd5f5] bg-white px-4 py-2 text-sm text-[#0f172a] shadow-sm focus:border-[#0a6fd6] focus:outline-none"
              placeholder="Question"
              value={item.question}
              onChange={(event) => updateItem(item.clientId, "question", event.target.value)}
            />
            <textarea
              className="mt-2 w-full rounded-xl border border-[#cbd5f5] bg-white px-4 py-2 text-sm text-[#0f172a] shadow-sm focus:border-[#0a6fd6] focus:outline-none"
              placeholder="Optional answer"
              rows={3}
              value={item.answer ?? ""}
              onChange={(event) => updateItem(item.clientId, "answer", event.target.value)}
            />
          </div>
        ))}
      </div>
      <button
        type="button"
        className="mt-4 w-full rounded-xl border border-dashed border-[#0a6fd6] px-4 py-2 text-sm font-semibold text-[#0a6fd6]"
        onClick={addFaq}
      >
        + Add FAQ entry
      </button>
    </section>
  );
};
