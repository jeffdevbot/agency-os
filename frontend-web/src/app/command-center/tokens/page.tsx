import { Suspense } from "react";
import { CostsSection } from "./sections/CostsSection";
import { InternalSection } from "./sections/InternalSection";
import { TokensHeader } from "./TokensHeader";
import { getSearchParam, parseAllowedRange, resolveSearchParams, type SearchParamsSource } from "../_lib/searchParams";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const LoadingCard = (props: { body: string }) => (
  <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
    <div className="animate-pulse space-y-3">
      <div className="h-5 w-40 rounded bg-slate-200" />
      <div className="h-4 w-64 rounded bg-slate-200" />
      <div className="mt-6 h-40 w-full rounded-2xl bg-slate-100" />
      <div className="text-xs text-[#4c576f]">{props.body}</div>
    </div>
  </div>
);

export default async function CommandCenterTokensPage(props: {
  searchParams?: SearchParamsSource;
}) {
  const searchParams = await resolveSearchParams(props.searchParams);
  const rangeDays = parseAllowedRange(getSearchParam(searchParams, "range"), [7, 30, 90], 7);

  return (
    <main className="space-y-6">
      <TokensHeader rangeDays={rangeDays} />

      <Suspense key={`costs-${rangeDays}`} fallback={<LoadingCard body="Fetching OpenAI costs…" />}>
        <CostsSection rangeDays={rangeDays} />
      </Suspense>

      <Suspense key={`internal-${rangeDays}`} fallback={<LoadingCard body="Querying internal logs…" />}>
        <InternalSection rangeDays={rangeDays} />
      </Suspense>
    </main>
  );
}
