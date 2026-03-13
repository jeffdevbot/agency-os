import type { ProfileIntegrationEditState } from "../workspaceTypes";

type Props = {
  profileIntegrationEdits: ProfileIntegrationEditState;
  saving: boolean;
  onFieldChange: <K extends keyof ProfileIntegrationEditState>(
    key: K,
    value: ProfileIntegrationEditState[K]
  ) => void;
  onSave: () => void;
};

export default function ProfileIntegrationsCard({
  profileIntegrationEdits,
  saving,
  onFieldChange,
  onSave,
}: Props) {
  return (
    <div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[#0f172a]">Profile Integrations</p>
          <p className="mt-1 text-sm text-[#4c576f]">
            Set source account identifiers here. Windsor import stays disabled until a Windsor
            account id is saved on the profile.
          </p>
        </div>
        <button
          onClick={onSave}
          disabled={saving}
          className="rounded-2xl bg-[#0a6fd6] px-4 py-3 text-sm font-semibold text-white shadow-[0_15px_30px_rgba(10,111,214,0.35)] transition hover:bg-[#0959ab] disabled:cursor-not-allowed disabled:bg-[#b7cbea]"
        >
          {saving ? "Saving..." : "Save Integrations"}
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Windsor Account ID</span>
          <input
            value={profileIntegrationEdits.windsor_account_id}
            onChange={(event) => onFieldChange("windsor_account_id", event.target.value)}
            placeholder="A3R8Q6L34VPOIB-US"
            className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
          />
        </label>

        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Amazon Ads Profile ID</span>
          <input
            value={profileIntegrationEdits.amazon_ads_profile_id}
            onChange={(event) => onFieldChange("amazon_ads_profile_id", event.target.value)}
            placeholder="Optional"
            className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
          />
        </label>

        <label className="text-sm">
          <span className="mb-1 block font-semibold text-[#0f172a]">Amazon Ads Account ID</span>
          <input
            value={profileIntegrationEdits.amazon_ads_account_id}
            onChange={(event) => onFieldChange("amazon_ads_account_id", event.target.value)}
            placeholder="Optional"
            className="w-full rounded-xl border border-[#c7d8f5] bg-[#f7faff] px-3 py-2 text-sm text-[#0f172a] outline-none ring-[#0a6fd6] focus:ring-2"
          />
        </label>
      </div>
    </div>
  );
}
