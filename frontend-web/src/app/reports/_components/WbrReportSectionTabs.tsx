"use client";

export type WbrReportSection = "traffic_sales" | "advertising" | "inventory_returns";

type SectionTab = {
  key: WbrReportSection;
  label: string;
};

type Props = {
  activeSection: WbrReportSection;
  onChange: (section: WbrReportSection) => void;
};

const SECTION_TABS: SectionTab[] = [
  { key: "traffic_sales", label: "Traffic + Sales" },
  { key: "advertising", label: "Advertising" },
  { key: "inventory_returns", label: "Inventory + Returns" },
];

export default function WbrReportSectionTabs({ activeSection, onChange }: Props) {
  return (
    <div className="rounded-3xl bg-white/95 p-3 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
      <div className="flex gap-2 overflow-x-auto">
        {SECTION_TABS.map((tab) => {
          const active = tab.key === activeSection;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onChange(tab.key)}
              className={`whitespace-nowrap rounded-2xl px-4 py-2 text-sm font-semibold transition md:px-5 md:py-2.5 ${
                active
                  ? "bg-[#0a6fd6] text-white shadow-[0_10px_30px_rgba(10,111,214,0.28)]"
                  : "border border-[#d8e4f8] bg-[#f7faff] text-[#4c576f] hover:border-[#b7cdee] hover:text-[#0f172a]"
              }`}
              aria-pressed={active}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
