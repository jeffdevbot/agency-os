"use client";

import Link from "next/link";
import AsinMappingCard from "./components/AsinMappingCard";
import CampaignExclusionCard from "./components/CampaignExclusionCard";
import CreateRowForm from "./components/CreateRowForm";
import LeafRowsTable from "./components/LeafRowsTable";
import ListingsImportCard from "./components/ListingsImportCard";
import PacvueImportCard from "./components/PacvueImportCard";
import ParentRowsTable from "./components/ParentRowsTable";
import ProfileIntegrationsCard from "./components/ProfileIntegrationsCard";
import ProfileSummaryCard from "./components/ProfileSummaryCard";
import { useAsinMappings } from "./useAsinMappings";
import { useCampaignExclusions } from "./useCampaignExclusions";
import { useListingImport } from "./useListingImport";
import { usePacvueImport } from "./usePacvueImport";
import { useWbrProfileWorkspace } from "./useWbrProfileWorkspace";
import type { WbrRowKind } from "./workspaceTypes";

type Props = {
  profileId: string;
  clientSlug?: string;
  marketplaceCode?: string;
};

export default function WbrProfileWorkspace({ profileId, clientSlug, marketplaceCode }: Props) {
  const workspace = useWbrProfileWorkspace(profileId);
  const asinMappings = useAsinMappings(profileId);
  const campaignExclusions = useCampaignExclusions(profileId);
  const listingImport = useListingImport(profileId, {
    onImportSuccess: async () => {
      await asinMappings.loadChildAsins(true);
    },
  });
  const pacvueImport = usePacvueImport(profileId, {
    onImportSuccess: async () => {
      await workspace.loadWorkspace(true);
    },
  });
  const normalizedMarketplace = marketplaceCode?.toLowerCase();
  const backHref = clientSlug ? `/reports/${clientSlug}` : "/reports/wbr";
  const reportHref =
    clientSlug && normalizedMarketplace
      ? `/reports/${clientSlug}/${normalizedMarketplace}/wbr`
      : "/reports/wbr";

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
            href={backHref}
            className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-[#0a6fd6] shadow transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            {clientSlug ? "Back to Marketplaces" : "Back to Setup"}
          </Link>
          <Link
            href={reportHref}
            className="rounded-2xl bg-[#e8eefc] px-4 py-3 text-sm font-semibold text-[#0f172a] transition hover:bg-[#d7e1fb]"
          >
            {clientSlug ? "Open WBR" : "Back to WBR"}
          </Link>
        </div>

        <ProfileSummaryCard profile={workspace.profile} />

        <ProfileIntegrationsCard
          profileIntegrationEdits={workspace.profileIntegrationEdits}
          saving={workspace.savingProfileIntegrations}
          onFieldChange={workspace.updateProfileIntegrationField}
          onSave={() => void workspace.handleSaveProfileIntegrations()}
        />

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

        <PacvueImportCard
          loadingBatches={pacvueImport.loadingBatches}
          refreshingBatches={pacvueImport.refreshingBatches}
          uploading={pacvueImport.uploading}
          creatingSnapshot={pacvueImport.creatingSnapshot}
          batches={pacvueImport.batches}
          errorMessage={pacvueImport.errorMessage}
          successMessage={pacvueImport.successMessage}
          latestImport={pacvueImport.latestImport}
          onRefresh={() => void pacvueImport.loadBatches(true)}
          onUpload={(file) => void pacvueImport.handleUpload(file)}
          onCreateFreshSnapshot={() => void pacvueImport.handleCreateFreshSnapshot()}
        />

        <CampaignExclusionCard
          loading={campaignExclusions.loading}
          refreshing={campaignExclusions.refreshing}
          exportingCsv={campaignExclusions.exportingCsv}
          importingCsv={campaignExclusions.importingCsv}
          items={campaignExclusions.items}
          errorMessage={campaignExclusions.errorMessage}
          successMessage={campaignExclusions.successMessage}
          latestImportSummary={campaignExclusions.latestImportSummary}
          onRefresh={() => void campaignExclusions.loadItems(true)}
          onDownloadCsv={() => void campaignExclusions.downloadCsv()}
          onUploadCsv={(file) => void campaignExclusions.uploadCsv(file)}
        />

        <ListingsImportCard
          windsorAccountId={workspace.profile?.windsor_account_id ?? null}
          loadingBatches={listingImport.loadingBatches}
          refreshingBatches={listingImport.refreshingBatches}
          uploading={listingImport.uploading}
          batches={listingImport.batches}
          errorMessage={listingImport.errorMessage}
          successMessage={listingImport.successMessage}
          latestImport={listingImport.latestImport}
          onRefresh={() => void listingImport.loadBatches(true)}
          onUpload={(file) => void listingImport.handleUpload(file)}
          onImportFromWindsor={() => void listingImport.handleWindsorImport(workspace.profile?.windsor_account_id)}
        />

        <AsinMappingCard
          loading={asinMappings.loading}
          refreshing={asinMappings.refreshing}
          errorMessage={asinMappings.errorMessage}
          successMessage={asinMappings.successMessage}
          childAsins={asinMappings.filteredChildAsins}
          counts={asinMappings.counts}
          search={asinMappings.search}
          unmappedOnly={asinMappings.unmappedOnly}
          draftRowIds={asinMappings.draftRowIds}
          savingRows={asinMappings.savingRows}
          importingCsv={asinMappings.importingCsv}
          exportingCsv={asinMappings.exportingCsv}
          latestCsvImportSummary={asinMappings.latestCsvImportSummary}
          leafRows={workspace.leafRows}
          onSearchChange={asinMappings.setSearch}
          onUnmappedOnlyChange={asinMappings.setUnmappedOnly}
          onDraftRowIdChange={asinMappings.updateDraftRowId}
          onSaveMapping={(item) => void asinMappings.saveMapping(item)}
          onRefresh={() => void asinMappings.loadChildAsins(true)}
          onDownloadCsv={() => void asinMappings.downloadMappingCsv()}
          onUploadCsv={(file) => void asinMappings.uploadMappingCsv(file)}
        />

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
