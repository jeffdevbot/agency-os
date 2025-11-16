"use client";

import { useCallback, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

if (!BACKEND_URL) {
  throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
}

export default function NgramPage() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = useCallback((file: File | null) => {
    setSelectedFile(file);
    setError(null);
  }, []);

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) {
      handleFileChange(file);
    }
  }, [handleFileChange]);

  const startUpload = useCallback(async () => {
    if (!selectedFile || uploading) {
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const accessToken = sessionData.session?.access_token;
      if (!accessToken) {
        setError("Please sign in again.");
        setUploading(false);
        return;
      }

      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${BACKEND_URL}/ngram/process`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => undefined);
        throw new Error(detail?.detail || "Upload failed");
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `${selectedFile.name.replace(/\.[^.]+$/, "")}_ngrams.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
      setToast("Download started");
      setTimeout(() => setToast(null), 3000);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }, [selectedFile, supabase, uploading]);

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <div className="px-6 py-8">
        <p className="text-xs font-semibold uppercase tracking-[0.4em] text-[#4c576f]">
          Agency OS
        </p>
        <h1 className="mt-3 text-4xl font-semibold text-[#0f172a]">N-Gram Processor</h1>
        <p className="mt-2 max-w-2xl text-sm text-[#4c576f]">
          Upload your Search Term Report to generate an Excel workbook with Monogram, Bigram, and Trigram analysis for each campaign.
        </p>
      </div>

      <div className="flex flex-1 items-start justify-center px-4 pb-16">
        <div className="w-full max-w-2xl rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="rounded-2xl border border-dashed border-[#c7d8f5] bg-[#f7faff] p-10 text-center"
          >
            <p className="text-base font-semibold text-[#0f172a]">Drag & drop your Search Term Report</p>
            <p className="text-sm text-[#4c576f]">(.xlsx, .xls, .csv)</p>
            <div className="mt-4 flex flex-col items-center gap-3">
              <label className="cursor-pointer rounded-full bg-white px-5 py-2 text-sm font-semibold text-[#0a6fd6] shadow">
                <input
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  className="hidden"
                  onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                />
                Browse files
              </label>
              <p className="text-xs text-[#94a3b8]">
                {selectedFile ? selectedFile.name : "No file selected"}
              </p>
            </div>
          </div>

          <button
            onClick={startUpload}
            disabled={!selectedFile || uploading}
            className="mt-8 w-full rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
          >
            {uploading ? "Processing…" : "Generate Report"}
          </button>

          {error && (
            <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
              {error}
            </p>
          )}
        </div>
      </div>

      {toast && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full bg-[#0a6fd6] px-6 py-3 text-sm font-semibold text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  );
}
