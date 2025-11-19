import type { StrategyType } from "@agency/lib/composer/types";

interface StrategyToggleProps {
  value: StrategyType | null;
  onChange: (strategy: StrategyType) => void;
  disabled?: boolean;
}

export const StrategyToggle = ({ value, onChange, disabled }: StrategyToggleProps) => {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-[#0f172a]">Content Strategy</h3>
      <p className="text-sm text-[#475569]">
        Choose how content will be generated for your SKUs.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => onChange("variations")}
          disabled={disabled}
          className={`rounded-xl border-2 p-4 text-left transition ${
            value === "variations"
              ? "border-[#0a6fd6] bg-[#eef2ff]"
              : "border-[#e2e8f0] bg-white hover:border-[#cbd5e1]"
          } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
        >
          <p className="font-semibold text-[#0f172a]">Variations</p>
          <p className="mt-1 text-sm text-[#475569]">
            Generate content for all SKUs together. Best for products that are minor
            variations of the same item (e.g., different colors or sizes).
          </p>
        </button>
        <button
          type="button"
          onClick={() => onChange("distinct")}
          disabled={disabled}
          className={`rounded-xl border-2 p-4 text-left transition ${
            value === "distinct"
              ? "border-[#0a6fd6] bg-[#eef2ff]"
              : "border-[#e2e8f0] bg-white hover:border-[#cbd5e1]"
          } ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
        >
          <p className="font-semibold text-[#0f172a]">Distinct</p>
          <p className="mt-1 text-sm text-[#475569]">
            Group SKUs and generate unique content per group. Best for products that are
            meaningfully different and need distinct messaging.
          </p>
        </button>
      </div>
    </div>
  );
};
