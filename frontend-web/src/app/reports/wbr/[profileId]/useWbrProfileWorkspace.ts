"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getBrowserSupabaseClient } from "@/lib/supabaseClient";
import {
  createWbrRow,
  deleteWbrRow,
  getWbrProfile,
  listWbrRows,
  updateWbrProfile,
  updateWbrRow,
} from "../_lib/wbrApi";
import type {
  ProfileIntegrationEditState,
  RowEditState,
  WbrProfile,
  WbrRow,
  WbrRowKind,
} from "./workspaceTypes";

const sortByOrderThenLabel = (a: WbrRow, b: WbrRow): number => {
  const orderCompare = a.sort_order - b.sort_order;
  if (orderCompare !== 0) return orderCompare;
  return a.row_label.localeCompare(b.row_label);
};

const buildEdits = (rows: WbrRow[]): Record<string, RowEditState> =>
  Object.fromEntries(
    rows.map((row) => [
      row.id,
      {
        row_label: row.row_label,
        parent_row_id: row.parent_row_id,
        sort_order: String(row.sort_order),
        active: row.active,
      },
    ])
  );

const buildProfileIntegrationEdits = (
  profile: WbrProfile | null
): ProfileIntegrationEditState => ({
  windsor_account_id: profile?.windsor_account_id ?? "",
  amazon_ads_profile_id: profile?.amazon_ads_profile_id ?? "",
  amazon_ads_account_id: profile?.amazon_ads_account_id ?? "",
});

export function useWbrProfileWorkspace(profileId: string) {
  const supabase = useMemo(() => getBrowserSupabaseClient(), []);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [profile, setProfile] = useState<WbrProfile | null>(null);
  const [profileIntegrationEdits, setProfileIntegrationEdits] = useState<ProfileIntegrationEditState>(
    buildProfileIntegrationEdits(null)
  );
  const [savingProfileIntegrations, setSavingProfileIntegrations] = useState(false);
  const [rows, setRows] = useState<WbrRow[]>([]);
  const [rowEdits, setRowEdits] = useState<Record<string, RowEditState>>({});
  const [savingRows, setSavingRows] = useState<Record<string, boolean>>({});
  const [isCreatingRow, setIsCreatingRow] = useState(false);
  const [newRowLabel, setNewRowLabel] = useState("");
  const [newRowKind, setNewRowKind] = useState<WbrRowKind>("leaf");
  const [newRowParentId, setNewRowParentId] = useState("");
  const [newRowSortOrder, setNewRowSortOrder] = useState("0");

  const parentRows = useMemo(
    () => rows.filter((row) => row.row_kind === "parent").sort(sortByOrderThenLabel),
    [rows]
  );
  const activeParentRows = useMemo(
    () => parentRows.filter((row) => row.active),
    [parentRows]
  );
  const leafRows = useMemo(
    () => rows.filter((row) => row.row_kind === "leaf").sort(sortByOrderThenLabel),
    [rows]
  );
  const parentById = useMemo(() => Object.fromEntries(parentRows.map((row) => [row.id, row])), [parentRows]);
  const activeParentIdSet = useMemo(() => new Set(activeParentRows.map((row) => row.id)), [activeParentRows]);
  const parentLabelById = useMemo(
    () => Object.fromEntries(parentRows.map((row) => [row.id, row.row_label])),
    [parentRows]
  );

  const getAccessToken = useCallback(async (): Promise<string> => {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.access_token) {
      throw new Error("Please sign in again.");
    }

    return session.access_token;
  }, [supabase]);

  const loadWorkspace = useCallback(
    async (isRefresh: boolean) => {
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setErrorMessage(null);

      try {
        const token = await getAccessToken();
        const [loadedProfile, loadedRows] = await Promise.all([
          getWbrProfile(token, profileId),
          listWbrRows(token, profileId),
        ]);
        const sortedRows = loadedRows.slice().sort(sortByOrderThenLabel);
        setProfile(loadedProfile);
        setProfileIntegrationEdits(buildProfileIntegrationEdits(loadedProfile));
        setRows(sortedRows);
        setRowEdits(buildEdits(sortedRows));
      } catch (error) {
        setProfile(null);
        setProfileIntegrationEdits(buildProfileIntegrationEdits(null));
        setRows([]);
        setRowEdits({});
        setErrorMessage(error instanceof Error ? error.message : "Unable to load profile workspace");
      } finally {
        if (isRefresh) {
          setRefreshing(false);
        } else {
          setLoading(false);
        }
      }
    },
    [getAccessToken, profileId]
  );

  useEffect(() => {
    void loadWorkspace(false);
  }, [loadWorkspace]);

  useEffect(() => {
    if (!newRowParentId) return;
    if (activeParentIdSet.has(newRowParentId)) return;
    setNewRowParentId("");
  }, [activeParentIdSet, newRowParentId]);

  const setCreateRowKind = (kind: WbrRowKind) => {
    setNewRowKind(kind);
    if (kind === "parent") {
      setNewRowParentId("");
    }
  };

  const handleCreateRow = async () => {
    if (!newRowLabel.trim()) {
      setErrorMessage("Row label is required.");
      return;
    }

    const parsedSort = Number(newRowSortOrder);
    if (!Number.isInteger(parsedSort)) {
      setErrorMessage("Sort order must be an integer.");
      return;
    }

    setIsCreatingRow(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      await createWbrRow(token, profileId, {
        row_label: newRowLabel.trim(),
        row_kind: newRowKind,
        parent_row_id: newRowKind === "leaf" ? newRowParentId || null : null,
        sort_order: parsedSort,
      });

      setNewRowLabel("");
      setCreateRowKind("leaf");
      setNewRowParentId("");
      setNewRowSortOrder("0");
      setSuccessMessage("Row created.");
      await loadWorkspace(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to create row");
    } finally {
      setIsCreatingRow(false);
    }
  };

  const updateRowField = <K extends keyof RowEditState>(rowId: string, key: K, value: RowEditState[K]) => {
    setRowEdits((prev) => ({
      ...prev,
      [rowId]: {
        ...prev[rowId],
        [key]: value,
      },
    }));
  };

  const updateProfileIntegrationField = <K extends keyof ProfileIntegrationEditState>(
    key: K,
    value: ProfileIntegrationEditState[K]
  ) => {
    setProfileIntegrationEdits((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSaveProfileIntegrations = async () => {
    if (!profile) {
      setErrorMessage("Profile is not loaded.");
      return;
    }

    setSavingProfileIntegrations(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      const updatedProfile = await updateWbrProfile(token, profile.id, {
        windsor_account_id: profileIntegrationEdits.windsor_account_id.trim() || null,
        amazon_ads_profile_id: profileIntegrationEdits.amazon_ads_profile_id.trim() || null,
        amazon_ads_account_id: profileIntegrationEdits.amazon_ads_account_id.trim() || null,
      });

      setProfile(updatedProfile);
      setProfileIntegrationEdits(buildProfileIntegrationEdits(updatedProfile));
      setSuccessMessage("Profile integrations saved.");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save profile integrations");
    } finally {
      setSavingProfileIntegrations(false);
    }
  };

  const handleSaveRow = async (row: WbrRow) => {
    const edit = rowEdits[row.id];
    if (!edit) return;

    if (!edit.row_label.trim()) {
      setErrorMessage("Row label is required.");
      return;
    }

    const parsedSort = Number(edit.sort_order);
    if (!Number.isInteger(parsedSort)) {
      setErrorMessage("Sort order must be an integer.");
      return;
    }

    const isNewInactiveParentAssignment =
      row.row_kind === "leaf" &&
      edit.parent_row_id !== null &&
      !activeParentIdSet.has(edit.parent_row_id) &&
      edit.parent_row_id !== row.parent_row_id;
    if (isNewInactiveParentAssignment) {
      setErrorMessage("Inactive parent rows cannot be assigned.");
      return;
    }

    setSavingRows((prev) => ({ ...prev, [row.id]: true }));
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      await updateWbrRow(token, row.id, {
        row_label: edit.row_label.trim(),
        parent_row_id: row.row_kind === "leaf" ? edit.parent_row_id : null,
        sort_order: parsedSort,
        active: edit.active,
      });
      setSuccessMessage(`Saved "${edit.row_label.trim()}".`);
      await loadWorkspace(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to save row");
    } finally {
      setSavingRows((prev) => ({ ...prev, [row.id]: false }));
    }
  };

  const handleDeactivateRow = async (row: WbrRow) => {
    if (!row.active) {
      setErrorMessage(`"${row.row_label}" is already inactive.`);
      return;
    }

    const confirmed = window.confirm(`Deactivate "${row.row_label}"?`);
    if (!confirmed) return;

    setSavingRows((prev) => ({ ...prev, [row.id]: true }));
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      await deleteWbrRow(token, row.id);
      setSuccessMessage(`Deactivated "${row.row_label}".`);
      await loadWorkspace(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to deactivate row");
    } finally {
      setSavingRows((prev) => ({ ...prev, [row.id]: false }));
    }
  };

  const handleDeleteRowPermanently = async (row: WbrRow) => {
    const confirmed = window.confirm(
      `Permanently delete "${row.row_label}"? This cannot be undone.`
    );
    if (!confirmed) return;

    setSavingRows((prev) => ({ ...prev, [row.id]: true }));
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const token = await getAccessToken();
      await deleteWbrRow(token, row.id, { permanent: true });
      setSuccessMessage(`Deleted "${row.row_label}" permanently.`);
      await loadWorkspace(true);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to permanently delete row");
    } finally {
      setSavingRows((prev) => ({ ...prev, [row.id]: false }));
    }
  };

  return {
    loading,
    refreshing,
    errorMessage,
    successMessage,
    profile,
    profileIntegrationEdits,
    savingProfileIntegrations,
    parentRows,
    activeParentRows,
    leafRows,
    parentById,
    parentLabelById,
    rowEdits,
    savingRows,
    isCreatingRow,
    newRowLabel,
    newRowKind,
    newRowParentId,
    newRowSortOrder,
    loadWorkspace,
    handleCreateRow,
    handleSaveProfileIntegrations,
    handleSaveRow,
    handleDeactivateRow,
    handleDeleteRowPermanently,
    setNewRowLabel,
    setCreateRowKind,
    setNewRowParentId,
    setNewRowSortOrder,
    updateProfileIntegrationField,
    updateRowField,
  };
}
