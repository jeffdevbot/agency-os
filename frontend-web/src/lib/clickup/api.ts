type ClickUpServiceCreateTaskResponse = {
  id: string;
  url?: string | null;
};

const getBackendUrl = (): string => {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not configured");
  }
  return url;
};

export const createClickUpTask = async (params: {
  accessToken: string;
  listId?: string | null;
  spaceId?: string | null;
  overrideListId?: string | null;
  name: string;
  description?: string | null;
  assigneeIds?: Array<string | number> | null;
}): Promise<ClickUpServiceCreateTaskResponse> => {
  const { accessToken, listId, spaceId, overrideListId, name, description, assigneeIds } = params;

  const normalizedAssignees = (assigneeIds ?? [])
    .map((id) => String(id).trim())
    .filter((id) => id.length > 0);

  const response = await fetch(`${getBackendUrl()}/clickup/tasks`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      list_id: listId ?? null,
      space_id: spaceId ?? null,
      override_list_id: overrideListId ?? null,
      name,
      description_md: description ?? null,
      assignee_ids: normalizedAssignees,
    }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`ClickUp service error (${response.status}): ${text || response.statusText}`);
  }

  const data = (await response.json()) as ClickUpServiceCreateTaskResponse;
  if (!data?.id) {
    throw new Error("ClickUp service returned no task id");
  }
  return data;
};
