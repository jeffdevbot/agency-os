import type { WbrProfile } from "../workspaceTypes";

type Props = {
  profile: WbrProfile | null;
};

export default function ProfileSummaryCard({ profile }: Props) {
  if (!profile) return null;

  return (
    <div className="mt-6 rounded-2xl border border-[#c7d8f5] bg-[#f7faff] p-5">
      <p className="text-sm font-semibold text-[#0f172a]">Profile</p>
      <div className="mt-2 grid gap-2 text-sm text-[#4c576f] md:grid-cols-2">
        <p>
          <span className="font-semibold text-[#0f172a]">Display:</span> {profile.display_name}
        </p>
        <p>
          <span className="font-semibold text-[#0f172a]">Marketplace:</span> {profile.marketplace_code}
        </p>
        <p>
          <span className="font-semibold text-[#0f172a]">Week Start:</span> {profile.week_start_day}
        </p>
        <p>
          <span className="font-semibold text-[#0f172a]">Status:</span> {profile.status}
        </p>
        <p>
          <span className="font-semibold text-[#0f172a]">Windsor Account:</span> {profile.windsor_account_id ?? "-"}
        </p>
        <p>
          <span className="font-semibold text-[#0f172a]">Amazon Ads Profile:</span>{" "}
          {profile.amazon_ads_profile_id ?? "-"}
        </p>
        <p>
          <span className="font-semibold text-[#0f172a]">Amazon Ads Account:</span>{" "}
          {profile.amazon_ads_account_id ?? "-"}
        </p>
        <p>
          <span className="font-semibold text-[#0f172a]">Daily Rewrite Days:</span> {profile.daily_rewrite_days}
        </p>
      </div>
    </div>
  );
}
