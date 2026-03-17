"use client";

import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { PnlFilterMode } from "../pnl/_lib/pnlApi";
import { FILTER_OPTIONS, formatMonth, formatMonthRangeLabel } from "../pnl/_lib/pnlDisplay";

type Props = {
  filterMode: PnlFilterMode;
  rangeStart: string;
  rangeEnd: string;
  onFilterModeChange: (value: PnlFilterMode) => void;
  onRangeStartChange: (value: string) => void;
  onRangeEndChange: (value: string) => void;
};

type PickerTarget = "start" | "end";

const FILTER_LABELS = new Map(FILTER_OPTIONS.map((option) => [option.value, option.label]));
const MONTH_OPTIONS = [
  { value: "01", label: "Jan" },
  { value: "02", label: "Feb" },
  { value: "03", label: "Mar" },
  { value: "04", label: "Apr" },
  { value: "05", label: "May" },
  { value: "06", label: "Jun" },
  { value: "07", label: "Jul" },
  { value: "08", label: "Aug" },
  { value: "09", label: "Sep" },
  { value: "10", label: "Oct" },
  { value: "11", label: "Nov" },
  { value: "12", label: "Dec" },
] as const;

function getYear(value: string): number {
  const parsed = Number.parseInt(value.slice(0, 4), 10);
  return Number.isFinite(parsed) ? parsed : new Date().getFullYear();
}

function clampYear(year: number, minYear: number, maxYear: number): number {
  return Math.min(Math.max(year, minYear), maxYear);
}

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

  const currentYear = new Date().getFullYear();
  const minYear = currentYear - 4;
  const maxYear = currentYear + 1;

  const [startYear, setStartYear] = useState(clampYear(getYear(rangeStart), minYear, maxYear));
  const [endYear, setEndYear] = useState(clampYear(getYear(rangeEnd), minYear, maxYear));

  useEffect(() => {
    setDraftStart(rangeStart.slice(0, 7));
    setDraftEnd(rangeEnd.slice(0, 7));
    setStartYear(clampYear(getYear(rangeStart), minYear, maxYear));
    setEndYear(clampYear(getYear(rangeEnd), minYear, maxYear));
  }, [maxYear, minYear, rangeEnd, rangeStart]);

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

  const yearSummary = useMemo(() => {
    const years = new Set([draftStart.slice(0, 4), draftEnd.slice(0, 4)].filter(Boolean));
    return Array.from(years).join(" - ");
  }, [draftEnd, draftStart]);

  const renderMonthGrid = (
    target: PickerTarget,
    year: number,
    value: string,
    setYear: (yearValue: number) => void,
    setValue: (next: string) => void,
  ) => (
    <div className="rounded-2xl border border-[#dbe4f0] bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#64748b]">
            {target === "start" ? "Start month" : "End month"}
          </p>
          <p className="mt-1 text-sm font-semibold text-[#0f172a]">
            {value ? formatMonth(`${value}-01`) : "Choose month"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setYear(clampYear(year - 1, minYear, maxYear))}
            disabled={year <= minYear}
            className="rounded-full border border-[#dbe4f0] p-2 text-[#475569] transition hover:border-[#94a3b8] hover:text-[#0f172a] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="min-w-[4.5rem] text-center text-sm font-semibold text-[#0f172a]">{year}</span>
          <button
            type="button"
            onClick={() => setYear(clampYear(year + 1, minYear, maxYear))}
            disabled={year >= maxYear}
            className="rounded-full border border-[#dbe4f0] p-2 text-[#475569] transition hover:border-[#94a3b8] hover:text-[#0f172a] disabled:cursor-not-allowed disabled:opacity-40"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        {MONTH_OPTIONS.map((month) => {
          const monthValue = `${year}-${month.value}`;
          const selected = value === monthValue;
          return (
            <button
              key={`${target}-${monthValue}`}
              type="button"
              onClick={() => setValue(monthValue)}
              className={`rounded-2xl px-3 py-3 text-sm font-semibold transition ${
                selected
                  ? "bg-[#0f172a] text-white"
                  : "bg-[#f8fafc] text-[#334155] hover:bg-[#eef2f7]"
              }`}
            >
              {month.label}
            </button>
          );
        })}
      </div>
    </div>
  );

  return (
    <div ref={rootRef} className="relative z-30">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex min-w-[15rem] items-center justify-between gap-2.5 rounded-[1.5rem] border border-[#dbe4f0] bg-white px-3.5 py-2.5 text-left shadow-sm transition hover:border-[#94a3b8] lg:min-w-[17.5rem]"
      >
        <span className="flex items-center gap-3">
          <span className="rounded-2xl bg-[#f7faff] p-2 text-[#0a6fd6]">
            <CalendarDays className="h-4.5 w-4.5" />
          </span>
          <span>
            <span className="block text-xs font-semibold uppercase tracking-[0.16em] text-[#64748b]">
              Reporting window
            </span>
            <span className="mt-0.5 block text-[0.9rem] font-semibold text-[#0f172a]">{triggerLabel}</span>
            {filterMode === "range" ? (
              <span className="block text-xs text-[#64748b]">{yearSummary}</span>
            ) : null}
          </span>
        </span>
        <ChevronDown
          className={`h-4 w-4 text-[#64748b] transition ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open ? (
        <div className="absolute right-0 z-50 mt-3 w-[min(46rem,calc(100vw-2rem))] rounded-3xl border border-[#dbe4f0] bg-white p-5 shadow-[0_30px_80px_rgba(10,59,130,0.18)]">
          <p className="text-base font-semibold text-[#0f172a]">Choose the reporting window</p>
          <p className="mt-1 text-sm text-[#64748b]">
            Use a preset for common views, or pick start and end months from the year-stepped month grid.
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            {FILTER_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => {
                  onFilterModeChange(option.value);
                  setOpen(false);
                }}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                  filterMode === option.value
                    ? "bg-[#0f172a] text-white"
                    : "bg-[#f8fafc] text-[#475569] hover:bg-[#eef2f7]"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="mt-5 rounded-3xl border border-[#e2e8f0] bg-[#f8fafc] p-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-[#334155]">Custom range</p>
                <p className="mt-1 text-sm text-[#64748b]">
                  Limited to recent operating years instead of an endless browser scroll.
                </p>
              </div>
              <div className="text-sm text-[#64748b]">
                {draftStart && draftEnd ? `${draftStart} to ${draftEnd}` : "Select both months"}
              </div>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              {renderMonthGrid("start", startYear, draftStart, setStartYear, setDraftStart)}
              {renderMonthGrid("end", endYear, draftEnd, setEndYear, setDraftEnd)}
            </div>

            <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              {hasInvalidRange ? (
                <p className="text-sm text-[#b45309]">Choose an end month after the start month.</p>
              ) : (
                <p className="text-sm text-[#64748b]">
                  The report refreshes as soon as you apply the new month span.
                </p>
              )}
              <button
                type="button"
                onClick={() => {
                  onRangeStartChange(`${draftStart}-01`);
                  onRangeEndChange(`${draftEnd}-01`);
                  onFilterModeChange("range");
                  setOpen(false);
                }}
                disabled={!draftStart || !draftEnd || hasInvalidRange}
                className="rounded-2xl bg-[#9a5b16] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#7f4a12] disabled:cursor-not-allowed disabled:opacity-50"
              >
                Apply custom range
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
