import type { WbrProfile, WbrRow, WbrRowKind } from "../_lib/wbrApi";

export type { WbrProfile, WbrRow, WbrRowKind };

export type RowEditState = {
  row_label: string;
  parent_row_id: string | null;
  sort_order: string;
  active: boolean;
};

export type ProfileIntegrationEditState = {
  windsor_account_id: string;
  amazon_ads_profile_id: string;
  amazon_ads_account_id: string;
};
