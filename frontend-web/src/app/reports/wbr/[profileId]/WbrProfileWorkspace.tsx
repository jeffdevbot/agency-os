"use client";

import Link from "next/link";
import CreateRowForm from "./components/CreateRowForm";
import LeafRowsTable from "./components/LeafRowsTable";
import ParentRowsTable from "./components/ParentRowsTable";
import ProfileSummaryCard from "./components/ProfileSummaryCard";
import { useWbrProfileWorkspace } from "./useWbrProfileWorkspace";
import type { WbrRowKind } from "./workspaceTypes";

type Props = {
  profileId: string;
};

export default function WbrProfileWorkspace({ profileId }: Props) {
  const workspace = useWbrProfileWorkspace(profileId);

  return (
    <main className="space-y-4">
      <div className="rounded-3xl bg-white/95 p-8 shadow-[0_30px_80px_rgba(10,59,130,0.15)] backdrop-blur">
        <h1 className="text-2xl font-semibold text-[#0f172a]">WBR Profile Workspace</h1>
        <p className="mt-2 text-sm text-[#4c576f]">Profile ID: {profileId}</p>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            onClick={() => void workspace.loadWorkspace(true)}
            disabled={workspace.loading || workspace.refreshing}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {workspace.refreshing ? "Refreshing..." : "Refresh"}
          </button>
          <Link
            href="/reports/wbr/setup"
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            Back to Setup
          </Link>
          <Link
            href="/reports/wbr"
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            Back to WBR
          </Link>
        </div>

        <ProfileSummaryCard profile={workspace.profile} />

        {workspace.errorMessage ? (
          <p className="mt-4 rounded-xl border border-[#f87171]/40 bg-[#fee2e2] px-4 py-3 text-sm text-[#991b1b]">
            {workspace.errorMessage}
          </p>
        ) : null}

        {workspace.successMessage ? (
          <p className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {workspace.successMessage}
          </p>
        ) : null}

        <CreateRowForm
          isCreatingRow={workspace.isCreatingRow}
          newRowLabel={workspace.newRowLabel}
          newRowKind={workspace.newRowKind}
          newRowParentId={workspace.newRowParentId}
          newRowSortOrder={workspace.newRowSortOrder}
          activeParentRows={workspace.activeParentRows}
          onNewRowLabelChange={workspace.setNewRowLabel}
          onNewRowKindChange={(value: WbrRowKind) => workspace.setCreateRowKind(value)}
          onNewRowParentIdChange={workspace.setNewRowParentId}
          onNewRowSortOrderChange={workspace.setNewRowSortOrder}
          onCreateRow={() => void workspace.handleCreateRow()}
        />

        <ParentRowsTable
          loading={workspace.loading}
          parentRows={workspace.parentRows}
          rowEdits={workspace.rowEdits}
          savingRows={workspace.savingRows}
          onRowLabelChange={(rowId, value) => workspace.updateRowField(rowId, "row_label", value)}
          onRowSortOrderChange={(rowId, value) => workspace.updateRowField(rowId, "sort_order", value)}
          onRowActiveChange={(rowId, value) => workspace.updateRowField(rowId, "active", value)}
          onSaveRow={(row) => void workspace.handleSaveRow(row)}
          onDeactivateRow={(row) => void workspace.handleDeactivateRow(row)}
          onDeleteRowPermanently={(row) => void workspace.handleDeleteRowPermanently(row)}
        />

        <LeafRowsTable
          loading={workspace.loading}
          leafRows={workspace.leafRows}
          activeParentRows={workspace.activeParentRows}
          parentById={workspace.parentById}
          parentLabelById={workspace.parentLabelById}
          rowEdits={workspace.rowEdits}
          savingRows={workspace.savingRows}
          onRowLabelChange={(rowId, value) => workspace.updateRowField(rowId, "row_label", value)}
          onRowParentChange={(rowId, value) => workspace.updateRowField(rowId, "parent_row_id", value)}
          onRowSortOrderChange={(rowId, value) => workspace.updateRowField(rowId, "sort_order", value)}
          onRowActiveChange={(rowId, value) => workspace.updateRowField(rowId, "active", value)}
          onSaveRow={(row) => void workspace.handleSaveRow(row)}
          onDeactivateRow={(row) => void workspace.handleDeactivateRow(row)}
          onDeleteRowPermanently={(row) => void workspace.handleDeleteRowPermanently(row)}
        />
      </div>
    </main>
  );
}
