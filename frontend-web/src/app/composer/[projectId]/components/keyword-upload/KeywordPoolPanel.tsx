"use client";

import { useMemo, useState } from "react";
import { parseKeywordsCsv, validateKeywordCount, mergeKeywords } from "@agency/lib/composer/keywords/utils";
import type { ComposerKeywordPool } from "@agency/lib/composer/types";

interface KeywordPoolPanelProps {
  poolType: "body" | "titles";
  title: string;
  description: string;
  pool: ComposerKeywordPool | undefined;
  isLoading: boolean;
  onUpload: (keywords: string[]) => Promise<{ warning?: string }>;
  onDelete: () => Promise<void>;
}

const formatCountLabel = (count: number) => `${count.toLocaleString()} keyword${count === 1 ? "" : "s"}`;

export const KeywordPoolPanel = ({
  poolType,
  title,
  description,
  pool,
  isLoading,
  onUpload,
  onDelete,
}: KeywordPoolPanelProps) => {
  const [pasteValue, setPasteValue] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const rawKeywords = pool?.rawKeywords ?? [];

  const statusBadge = useMemo(() => {
    const count = rawKeywords.length;
    if (count === 0) return { label: "Empty", tone: "bg-[#fee2e2] text-[#b91c1c]" };
    if (count < 5) return { label: "Below minimum", tone: "bg-[#fef3c7] text-[#b45309]" };
    if (count < 20) return { label: "Low volume", tone: "bg-[#fef3c7] text-[#b45309]" };
    return { label: "Ready for cleanup", tone: "bg-[#dcfce7] text-[#166534]" };
  }, [rawKeywords.length]);

  const previewKeywords = rawKeywords.slice(0, 20);

  const handleKeywords = async (keywords: string[]) => {
    setError(null);
    setMessage(null);
    if (keywords.length === 0) {
      setError("No keywords detected. Try again.");
      return;
    }

    const merged = mergeKeywords(rawKeywords, keywords);
    const validation = validateKeywordCount(merged);

    // Upload keywords regardless of count (allow iterative accumulation)
    setIsSubmitting(true);
    const result = await onUpload(keywords);
    setIsSubmitting(false);

    // Show appropriate message based on validation state
    const totalCount = merged.length;

    if (!validation.valid && validation.error) {
      // Show progress message for < 5 keywords (informational, not error)
      const remaining = 5 - totalCount;
      setMessage(
        `Uploaded ${keywords.length} keyword(s). Total: ${totalCount}/5. Upload ${remaining} more to proceed to cleanup.`
      );
    } else if (result.warning || validation.warning) {
      // Show warning for counts between 5-49 (recommend 50-100+)
      setMessage(result.warning ?? validation.warning ?? null);
    } else {
      // Success message for good counts (50+)
      setMessage(`Uploaded ${keywords.length} keyword(s)`);
    }

    setPasteValue("");
  };

  const decodeFileText = async (file: File): Promise<string> => {
    const buffer = await file.arrayBuffer();
    const view = new Uint8Array(buffer);

    // Detect BOM for UTF-16/UTF-8
    const hasUtf8Bom = view[0] === 0xef && view[1] === 0xbb && view[2] === 0xbf;
    const hasUtf16LeBom = view[0] === 0xff && view[1] === 0xfe;
    const hasUtf16BeBom = view[0] === 0xfe && view[1] === 0xff;

    if (hasUtf16LeBom) {
      return new TextDecoder("utf-16le").decode(buffer);
    }
    if (hasUtf16BeBom) {
      return new TextDecoder("utf-16be").decode(buffer);
    }
    if (hasUtf8Bom) {
      return new TextDecoder("utf-8").decode(buffer);
    }

    const candidates: Array<{ encoding: string; text: string; replacements: number; nulls: number }> =
      [];
    for (const encoding of ["utf-8", "windows-1252", "latin1"]) {
      const decoder = new TextDecoder(encoding as BufferEncoding, { fatal: false });
      const text = decoder.decode(buffer);
      const replacements = (text.match(/\uFFFD/g) ?? []).length;
      const nulls = (text.match(/\u0000/g) ?? []).length;
      candidates.push({ encoding, text, replacements, nulls });
    }

    candidates.sort((a, b) => {
      if (a.replacements !== b.replacements) return a.replacements - b.replacements;
      if (a.nulls !== b.nulls) return a.nulls - b.nulls;
      // Prefer utf-8 if tied
      if (a.encoding === "utf-8") return -1;
      if (b.encoding === "utf-8") return 1;
      if (a.encoding === "windows-1252") return -1;
      if (b.encoding === "windows-1252") return 1;
      return 0;
    });

    const best = candidates[0];
    return best.text.replace(/\u0000/g, "");
  };

  const handleFileUpload = async (file: File) => {
    setFileError(null);
    if (file.size > 5 * 1024 * 1024) {
      setFileError("File too large. Max 5MB.");
      return;
    }

    const text = await decodeFileText(file);
    const parsed = parseKeywordsCsv(text);
    await handleKeywords(parsed);
  };

  const acceptText = poolType === "titles" ? "Titles CSV or text" : "Keywords CSV or text";

  return (
    <div className="rounded-2xl border border-[#e2e8f0] bg-[#f8fafc] p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-[#0f172a]">{title}</h3>
          <p className="text-sm text-[#475569]">{description}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusBadge.tone}`}>
          {statusBadge.label}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm text-[#475569] md:grid-cols-4">
        <div className="rounded-xl bg-white/70 p-3">
          <dt className="text-xs uppercase tracking-wide text-[#94a3b8]">Raw keywords</dt>
          <dd className="text-lg font-semibold text-[#0f172a]">{formatCountLabel(rawKeywords.length)}</dd>
        </div>
        <div className="rounded-xl bg-white/70 p-3">
          <dt className="text-xs uppercase tracking-wide text-[#94a3b8]">Cleaned</dt>
          <dd className="text-lg font-semibold text-[#0f172a]">
            {formatCountLabel(pool?.cleanedKeywords.length ?? 0)}
          </dd>
        </div>
        <div className="rounded-xl bg-white/70 p-3">
          <dt className="text-xs uppercase tracking-wide text-[#94a3b8]">Removed</dt>
          <dd className="text-lg font-semibold text-[#0f172a]">
            {formatCountLabel(pool?.removedKeywords.length ?? 0)}
          </dd>
        </div>
        <div className="rounded-xl bg-white/70 p-3">
          <dt className="text-xs uppercase tracking-wide text-[#94a3b8]">Status</dt>
          <dd className="text-lg font-semibold text-[#0f172a] capitalize">{pool?.status ?? "empty"}</dd>
        </div>
      </dl>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div
          className={`rounded-xl border border-dashed bg-white p-4 transition ${
            isDragging ? "border-[#0a6fd6] bg-[#eef2ff]" : "border-[#cbd5f5]"
          }`}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            setIsDragging(false);
          }}
          onDrop={async (event) => {
            event.preventDefault();
            setIsDragging(false);
            const file = event.dataTransfer.files?.[0];
            if (file) {
              await handleFileUpload(file);
            }
          }}
        >
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-[#0f172a]">Upload CSV</p>
              <p className="text-xs text-[#64748b]">{acceptText} (max 5MB)</p>
            </div>
            <a
              href="/composer/keyword_template.csv"
              download
              className="text-xs font-semibold text-[#0a6fd6] hover:underline"
            >
              Download Template
            </a>
          </div>
          <input
            type="file"
            accept=".csv,text/csv,text/plain"
            className="mt-3 w-full cursor-pointer text-sm"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (file) {
                await handleFileUpload(file);
                event.target.value = "";
              }
            }}
            disabled={isSubmitting || isLoading}
          />
          {fileError && <p className="mt-2 text-xs text-[#b91c1c]">{fileError}</p>}
        </div>

        <div className="rounded-xl border border-[#e2e8f0] bg-white p-4">
          <p className="text-sm font-semibold text-[#0f172a]">Paste keywords</p>
          <textarea
            className="mt-2 h-24 w-full rounded-xl border border-[#cbd5f5] p-2 text-sm text-[#0f172a] focus:border-[#0a6fd6] focus:outline-none"
            placeholder="One keyword per line"
            value={pasteValue}
            onChange={(e) => setPasteValue(e.target.value)}
            disabled={isSubmitting || isLoading}
          />
          <button
            className="mt-2 w-full rounded-full bg-[#0a6fd6] px-4 py-2 text-sm font-semibold text-white shadow disabled:opacity-40"
            onClick={async () => {
              const keywords = pasteValue
                .split(/\r?\n/)
                .map((k) => k.trim())
                .filter(Boolean);
              await handleKeywords(keywords);
            }}
            disabled={isSubmitting || isLoading}
          >
            Import from Paste
          </button>
        </div>
      </div>

      {(error || message) && (
        <div
          className={`mt-4 rounded-xl p-3 text-sm ${
            error ? "bg-[#fef2f2] text-[#b91c1c]" : "bg-[#fef3c7] text-[#92400e]"
          }`}
        >
          {error ?? message}
        </div>
      )}

      <div className="mt-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-[#0f172a]">Raw Preview</p>
          <div className="flex items-center gap-3 text-xs text-[#64748b]">
            <p>Showing {previewKeywords.length} of {rawKeywords.length}</p>
            <button
              className="rounded-full bg-[#fef2f2] px-3 py-1 text-xs font-semibold text-[#b91c1c] shadow disabled:opacity-40"
              onClick={() => void onDelete()}
              disabled={isSubmitting || isLoading || rawKeywords.length === 0}
              title="Delete all uploaded keywords for this pool"
            >
              Delete Keywords
            </button>
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {previewKeywords.length === 0 ? (
            <span className="text-sm text-[#94a3b8]">No keywords yet.</span>
          ) : (
            previewKeywords.map((keyword) => (
              <span
                key={keyword}
                className="rounded-full bg-white px-3 py-1 text-xs text-[#0f172a] shadow-sm"
              >
                {keyword}
              </span>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
