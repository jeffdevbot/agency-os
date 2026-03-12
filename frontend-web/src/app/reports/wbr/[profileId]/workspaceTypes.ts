import type { WbrProfile, WbrRow, WbrRowKind } from "../_lib/wbrApi";

export type { WbrProfile, WbrRow, WbrRowKind };

export type RowEditState = {
  row_label: string;
  parent_row_id: string | null;
  sort_order: string;
  active: boolean;
};
