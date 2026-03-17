"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { buildReportsHeaderState } from "../_lib/reportsHeaderState";

export default function ReportsHeader() {
  const pathname = usePathname();
  const headerState = buildReportsHeaderState(pathname);

  return (
    <header className="border-b border-slate-200 bg-white px-4 py-4 shadow-sm">
      <div className="mx-auto flex w-full max-w-[1560px] flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <Link href="/reports" className="flex flex-col">
          <span className="text-2xl font-extrabold leading-none text-[#0f172a]">
            {headerState.title}
          </span>
          <span className="mt-1 text-sm text-[#4c576f]">{headerState.subtitle}</span>
        </Link>

        <div className="flex flex-col items-start gap-3 lg:items-end">
          {headerState.surfaceLinks.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              {headerState.surfaceLinks.map((item) => (
                <Link
                  key={`${item.href}-${item.label}`}
                  href={item.href}
                  className={`rounded-full px-3 py-1.5 text-sm font-semibold transition ${
                    item.active
                      ? "bg-[#0f172a] text-white"
                      : "bg-[#e8eefc] text-[#0f172a] hover:bg-[#d7e1fb]"
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-4">
            {headerState.actionLinks.map((item) => (
              <Link
                key={`${item.href}-${item.label}`}
                href={item.href}
                className={`text-sm font-semibold hover:underline ${
                  item.active ? "text-[#0f172a]" : "text-[#0a6fd6]"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </header>
  );
}
