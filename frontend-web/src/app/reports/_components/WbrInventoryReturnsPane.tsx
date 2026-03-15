"use client";

import type { WbrSection1Week, WbrSection3Row } from "../wbr/_lib/wbrSection1Api";
import WbrSection3Table from "./WbrSection3Table";

type Props = {
  loading: boolean;
  rows: WbrSection3Row[];
  returnsWeeks: WbrSection1Week[];
  weekCount: number;
  hideEmptyRows: boolean;
  referenceRowOrder: string[];
};

const hasAnySection3Activity = (rows: WbrSection3Row[]): boolean =>
  rows.some(
    (r) =>
      r.instock > 0 ||
      r.working > 0 ||
      r.reserved_plus_fc_transfer > 0 ||
      r.receiving_plus_intransit > 0 ||
      r.returns_week_1 > 0 ||
      r.returns_week_2 > 0
  );

export default function WbrInventoryReturnsPane({
  loading,
  rows,
  returnsWeeks,
  weekCount,
  hideEmptyRows,
  referenceRowOrder,
}: Props) {
  if (loading) {
    return (
      <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="text-sm text-[#64748b]">Loading inventory and returns data...</p>
      </div>
    );
  }

  if (rows.length === 0 || !hasAnySection3Activity(rows)) {
    return (
      <div className="rounded-3xl bg-white/95 p-6 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          No inventory or returns data is showing. Run a Windsor sync from the Sync page.
        </p>
      </div>
    );
  }

  return (
    <WbrSection3Table
      returnsWeeks={returnsWeeks}
      rows={rows}
      weekCount={weekCount}
      hideEmptyRows={hideEmptyRows}
      referenceRowOrder={referenceRowOrder}
    />
  );
}
