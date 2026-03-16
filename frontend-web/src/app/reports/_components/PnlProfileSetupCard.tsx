"use client";

type Props = {
  marketplaceCode: string;
  createPending: boolean;
  createError: string | null;
  onCreateProfile: () => void;
};

export default function PnlProfileSetupCard({
  marketplaceCode,
  createPending,
  createError,
  onCreateProfile,
}: Props) {
  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="rounded-2xl border border-[#c7d2fe] bg-[#eef4ff] p-5">
        <h2 className="text-lg font-semibold text-[#0f172a]">Create Amazon P&amp;L profile</h2>
        <p className="mt-2 text-sm text-[#475569]">
          This marketplace does not have a P&amp;L profile yet. Create it here, then upload a
          monthly Amazon transaction report to backfill the report.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            onClick={onCreateProfile}
            disabled={createPending}
            className="rounded-xl bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab] disabled:opacity-50"
          >
            {createPending ? "Creating..." : `Create ${marketplaceCode.toUpperCase()} Amazon P&L`}
          </button>
        </div>
        {createError ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {createError}
          </p>
        ) : null}
      </div>
    </div>
  );
}
