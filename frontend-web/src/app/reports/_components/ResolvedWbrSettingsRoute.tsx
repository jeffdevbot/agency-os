"use client";

import { useResolvedWbrProfile } from "../_lib/useResolvedWbrProfile";
import WbrProfileWorkspace from "../wbr/[profileId]/WbrProfileWorkspace";

type Props = {
  clientSlug: string;
  marketplaceCode: string;
};

export default function ResolvedWbrSettingsRoute({ clientSlug, marketplaceCode }: Props) {
  const resolved = useResolvedWbrProfile(clientSlug, marketplaceCode);

  if (resolved.loading) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 text-sm text-[#64748b] shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          Loading WBR settings...
        </div>
      </main>
    );
  }

  if (!resolved.profile || !resolved.summary) {
    return (
      <main className="space-y-4">
        <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
          <h1 className="text-2xl font-semibold text-[#0f172a]">WBR Settings</h1>
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {resolved.errorMessage ?? "Unable to load WBR settings"}
          </p>
        </div>
      </main>
    );
  }

  return (
    <WbrProfileWorkspace
      profileId={resolved.profile.id}
      clientSlug={clientSlug}
      marketplaceCode={marketplaceCode}
    />
  );
}
