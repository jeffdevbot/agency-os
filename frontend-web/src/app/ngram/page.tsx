"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

if (!BACKEND_URL) {
  throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
}

export default function NgramPage() {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFilledFile, setSelectedFilledFile] = useState<File | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [collectError, setCollectError] = useState<string | null>(null);
  const [collecting, setCollecting] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("Generate Report");
  const phrasesRef = useRef([
    "Reticulating splines",
    "Calibrating flux capacitors",
    "Engaging hyperdrive motivator",
    "Adjusting recoil patterns",
    "Recalibrating arc reactor output",
  ]);

  useEffect(() => {
    if (!uploading) {
      setUploadStatus("Generate Report");
      return;
    }
    let idx = 0;
    setUploadStatus(phrasesRef.current[idx]);
    const id = setInterval(() => {
      idx = (idx + 1) % phrasesRef.current.length;
      setUploadStatus(phrasesRef.current[idx]);
    }, 1400);
    return () => clearInterval(id);
  }, [uploading]);

  const handleFileChange = useCallback((file: File | null) => {
    setSelectedFile(file);
    setError(null);
  }, []);

  const handleFilledFileChange = useCallback((file: File | null) => {
    setSelectedFilledFile(file);
    setCollectError(null);
  }, []);

  const handleDrop = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) {
      handleFileChange(file);
    }
  }, [handleFileChange]);

  const handleFilledDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const file = event.dataTransfer.files[0];
      if (file) {
        handleFilledFileChange(file);
      }
    },
    [handleFilledFileChange]
  );

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

  const startCollect = useCallback(async () => {
    if (!selectedFilledFile || collecting) {
      return;
    }
    setCollecting(true);
    setCollectError(null);
    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const accessToken = sessionData.session?.access_token;
      if (!accessToken) {
        setCollectError("Please sign in again.");
        setCollecting(false);
        return;
      }

      const formData = new FormData();
      formData.append("file", selectedFilledFile);

      const response = await fetch(`${BACKEND_URL}/ngram/collect`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => undefined);
        throw new Error(detail?.detail || "Collect failed");
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `${selectedFilledFile.name.replace(/\.[^.]+$/, "")}_negatives.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
      setToast("Negatives file downloaded");
      setTimeout(() => setToast(null), 3000);
    } catch (collectErr) {
      setCollectError(collectErr instanceof Error ? collectErr.message : "Collect failed");
    } finally {
      setCollecting(false);
    }
  }, [collecting, selectedFilledFile, supabase]);

  return (
    <div className="flex min-h-screen flex-col bg-gradient-to-br from-[#eaf2ff] via-[#dce8ff] to-[#cddcf8]">
      <header className="border-b border-slate-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-6xl items-baseline gap-3">
          <h1 className="text-xl font-bold tracking-tight text-slate-900">N-GRAM PROCESSOR</h1>
          <p className="text-sm text-slate-500">
            Upload your Search Term Report and export campaign n-gram insights.
          </p>
        </div>
      </header>

      <div className="flex flex-1 items-start justify-center px-4 pb-16 pt-10">
        <div className="w-full max-w-5xl space-y-10">
          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 1</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Generate the N-Gram workbook</h2>
              <p className="text-sm text-[#4c576f]">
                Upload your Search Term Report to create the campaign workbook with mono/bi/tri tables and NE scratchpads.
              </p>
            </div>
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              className="mt-6 rounded-2xl border border-dashed border-[#c7d8f5] bg-[#f7faff] p-10 text-center"
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
              className={`mt-6 w-full rounded-2xl px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea] ${
                uploading ? "bg-[#0a6fd6] ring-2 ring-offset-2 ring-[#8cc7ff] animate-pulse" : "bg-[#0a6fd6]"
              }`}
            >
              {uploading ? uploadStatus : "Generate Report"}
            </button>

            {error && (
              <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {error}
              </p>
            )}
          </div>

          <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#94a3b8]">Step 2</p>
              <h2 className="mt-1 text-lg font-semibold text-[#0f172a]">Upload the filled workbook to collect negatives</h2>
              <p className="text-sm text-[#4c576f]">
                After your team marks NE and fills the scratchpads, upload the completed workbook to export a single negatives summary per campaign.
              </p>
            </div>

            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleFilledDrop}
              className="mt-6 rounded-2xl border border-dashed border-[#c7d8f5] bg-[#f7faff] p-10 text-center"
            >
              <p className="text-base font-semibold text-[#0f172a]">Drag & drop your completed workbook</p>
              <p className="text-sm text-[#4c576f]">(.xlsx)</p>
              <div className="mt-4 flex flex-col items-center gap-3">
                <label className="cursor-pointer rounded-full bg-white px-5 py-2 text-sm font-semibold text-[#0a6fd6] shadow">
                  <input
                    type="file"
                    accept=".xlsx"
                    className="hidden"
                    onChange={(e) => handleFilledFileChange(e.target.files?.[0] ?? null)}
                  />
                  Browse files
                </label>
                <p className="text-xs text-[#94a3b8]">
                  {selectedFilledFile ? selectedFilledFile.name : "No file selected"}
                </p>
              </div>
            </div>

            <button
              onClick={startCollect}
              disabled={!selectedFilledFile || collecting}
              className="mt-6 w-full rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
            >
              {collecting ? "Collecting…" : "Download Negatives Summary"}
            </button>

            {collectError && (
              <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
                {collectError}
              </p>
            )}
          </div>
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
