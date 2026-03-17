"use client";

type Props = {
  selectedFileName: string | null;
  uploadPending: boolean;
  uploadError: string | null;
  uploadSuccess: string | null;
  processingStatus: string | null;
  processingLines: string[];
  onFileChange: (file: File | null) => void;
  onUpload: () => void;
};

export default function PnlUploadCard({
  selectedFileName,
  uploadPending,
  uploadError,
  uploadSuccess,
  processingStatus,
  processingLines,
  onFileChange,
  onUpload,
}: Props) {
  return (
    <div className="rounded-3xl bg-white/95 p-5 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur md:p-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#0f172a]">Backfill transaction report</h2>
          <p className="mt-1 text-sm text-[#475569]">
            Upload the Amazon Monthly Unified Transaction Report CSV for this marketplace.
          </p>
          <p className="mt-2 text-sm text-[#64748b]">
            Different Amazon download dates can shift settlement coverage for the same month, so
            reconcile against the same source export when comparing to a manual workbook.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <label className="rounded-xl border border-[#dbe4f0] bg-white px-4 py-2 text-sm font-medium text-[#334155] transition hover:border-[#94a3b8]">
            <input
              type="file"
              accept=".csv,.txt,.tsv"
              className="hidden"
              onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
            />
            {selectedFileName ?? "Choose file"}
          </label>
          <button
            onClick={onUpload}
            disabled={!selectedFileName || uploadPending}
            aria-busy={uploadPending}
            className={`rounded-xl px-4 py-2 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.2)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea] ${
              uploadPending
                ? "bg-[#0a6fd6] ring-2 ring-offset-2 ring-[#8cc7ff] animate-pulse"
                : "bg-[#0a6fd6]"
            }`}
          >
            {uploadPending ? "Uploading..." : "Upload report"}
          </button>
        </div>
      </div>

      {uploadSuccess ? (
        <p className="mt-4 rounded-xl border border-[#86efac]/40 bg-[#dcfce7] px-4 py-3 text-sm text-[#166534]">
          {uploadSuccess}
        </p>
      ) : null}
      {processingStatus ? (
        <div className="mt-4 rounded-xl border border-[#0a6fd6]/20 bg-[#eff6ff] px-4 py-3 text-sm text-[#0f172a]">
          <p>
            Background import status:
            {" "}
            <span className="font-semibold capitalize">{processingStatus}</span>
          </p>
          {processingLines.map((line) => (
            <p key={line} className="mt-1 text-[#334155]">
              {line}
            </p>
          ))}
        </div>
      ) : null}
      {uploadError ? (
        <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
          {uploadError}
        </p>
      ) : null}
    </div>
  );
}
