"use client";

import { CalendarDays, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { PnlFilterMode } from "../pnl/_lib/pnlApi";
import { FILTER_OPTIONS, formatMonthRangeLabel } from "../pnl/_lib/pnlDisplay";

type Props = {
  filterMode: PnlFilterMode;
  rangeStart: string;
  rangeEnd: string;
  onFilterModeChange: (value: PnlFilterMode) => void;
  onRangeStartChange: (value: string) => void;
  onRangeEndChange: (value: string) => void;
};

const FILTER_LABELS = new Map(FILTER_OPTIONS.map((option) => [option.value, option.label]));

export default function PnlMonthRangePicker({
  filterMode,
  rangeStart,
  rangeEnd,
  onFilterModeChange,
  onRangeStartChange,
  onRangeEndChange,
}: Props) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [open, setOpen] = useState(false);
  const [draftStart, setDraftStart] = useState(rangeStart.slice(0, 7));
  const [draftEnd, setDraftEnd] = useState(rangeEnd.slice(0, 7));

  useEffect(() => {
    setDraftStart(rangeStart.slice(0, 7));
    setDraftEnd(rangeEnd.slice(0, 7));
  }, [rangeEnd, rangeStart]);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    window.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("keydown", handleEscape);
    return () => {
      window.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  const triggerLabel =
    filterMode === "range"
      ? formatMonthRangeLabel(rangeStart, rangeEnd)
      : FILTER_LABELS.get(filterMode) ?? "Month range";
  const hasInvalidRange = Boolean(draftStart && draftEnd && draftStart > draftEnd);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex min-w-[16rem] items-center justify-between gap-3 rounded-2xl border border-[#dbe4f0] bg-white px-4 py-3 text-left shadow-sm transition hover:border-[#94a3b8]"
      >
        <span className="flex items-center gap-3">
          <span className="rounded-xl bg-[#f7faff] p-2 text-[#0a6fd6]">
            <CalendarDays className="h-4 w-4" />
          </span>
          <span>
            <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-[#64748b]">
              Month range
            </span>
            <span className="block text-sm font-semibold text-[#0f172a]">{triggerLabel}</span>
          </span>
        </span>
        <ChevronDown
          className={`h-4 w-4 text-[#64748b] transition ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open ? (
        <div className="absolute right-0 z-20 mt-3 w-[min(22rem,calc(100vw-2rem))] rounded-3xl border border-[#dbe4f0] bg-white p-4 shadow-[0_30px_80px_rgba(10,59,130,0.18)]">
          <p className="text-sm font-semibold text-[#0f172a]">Choose the reporting window</p>
          <p className="mt-1 text-sm text-[#64748b]">
            Default view is the last 3 months. Switch presets or choose a custom month span.
          </p>

          <div className="mt-4 grid grid-cols-2 gap-2">
            {FILTER_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onFilterModeChange(option.value);
                  setOpen(false);
                }}
                className={`rounded-2xl px-3 py-2 text-sm font-medium transition ${
                  filterMode === option.value
                    ? "bg-[#0f172a] text-white"
                    : "bg-[#f8fafc] text-[#475569] hover:bg-[#eef2f7]"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="mt-4 rounded-2xl border border-[#e2e8f0] bg-[#f8fafc] p-4">
            <p className="text-sm font-semibold text-[#334155]">Custom range</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-sm text-[#475569]">
                <span className="mb-1 block">From</span>
                <input
                  type="month"
                  value={draftStart}
                  onChange={(event) => setDraftStart(event.target.value)}
                  className="w-full rounded-xl border border-[#dbe4f0] bg-white px-3 py-2 text-sm text-[#0f172a]"
                />
              </label>
              <label className="text-sm text-[#475569]">
                <span className="mb-1 block">To</span>
                <input
                  type="month"
                  value={draftEnd}
                  onChange={(event) => setDraftEnd(event.target.value)}
                  className="w-full rounded-xl border border-[#dbe4f0] bg-white px-3 py-2 text-sm text-[#0f172a]"
                />
              </label>
            </div>

            <button
              type="button"
              onClick={() => {
                onRangeStartChange(`${draftStart}-01`);
                onRangeEndChange(`${draftEnd}-01`);
                onFilterModeChange("range");
                setOpen(false);
              }}
              disabled={!draftStart || !draftEnd || hasInvalidRange}
              className="mt-4 w-full rounded-2xl bg-[#9a5b16] px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#7f4a12] disabled:cursor-not-allowed disabled:opacity-50"
            >
              Apply custom range
            </button>
            {hasInvalidRange ? (
              <p className="mt-2 text-xs text-[#b45309]">Choose an end month after the start month.</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
