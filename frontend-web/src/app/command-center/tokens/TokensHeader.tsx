"use client";

import { useEffect, useState, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

const RANGE_OPTIONS = [
  { days: 7, label: "Last 7 days" },
  { days: 30, label: "Last 30 days" },
  { days: 90, label: "Last 90 days" },
] as const;

export function TokensHeader(props: { rangeDays: number }) {
  const { rangeDays } = props;
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [localRange, setLocalRange] = useState(rangeDays);

  useEffect(() => {
    setLocalRange(rangeDays);
  }, [rangeDays]);

  const onChange = (nextDays: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("range", String(nextDays));
    setLocalRange(nextDays);
    startTransition(() => {
      router.replace(`${pathname}?${params.toString()}`);
      router.refresh();
    });
  };

  return (
    <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[#0f172a]">Token Usage</h1>
          <p className="mt-2 text-sm text-[#4c576f]">Official spend vs. Internal tracking</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold uppercase tracking-wide text-[#4c576f]">Range</label>
          <select
            value={localRange}
            onChange={(e) => onChange(Number(e.target.value))}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-[#0f172a] shadow"
            disabled={isPending}
          >
            {RANGE_OPTIONS.map((opt) => (
              <option key={opt.days} value={opt.days}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
