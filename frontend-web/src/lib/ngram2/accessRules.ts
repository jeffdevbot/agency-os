export const NGRAM2_TOOL_SLUG = "ngram-2";

export const normalizeAllowedTools = (value: unknown): string[] => {
  if (!Array.isArray(value)) return [];

  return Array.from(
    new Set(
      value
        .map((entry) => (typeof entry === "string" ? entry.trim().toLowerCase() : ""))
        .filter(Boolean),
    ),
  );
};

export const hasAllowedTool = (allowedTools: string[], toolSlug: string): boolean =>
  normalizeAllowedTools(allowedTools).includes(toolSlug.trim().toLowerCase());

export const canAccessNgram2 = (profile: {
  isAdmin: boolean;
  allowedTools: string[];
}): boolean => profile.isAdmin || hasAllowedTool(profile.allowedTools, NGRAM2_TOOL_SLUG);

export const collectAssignedClientIds = (
  assignments: Array<{ clientId: string; teamMemberId: string }>,
  teamMemberId: string,
): string[] =>
  Array.from(
    new Set(
      assignments
        .filter((assignment) => assignment.teamMemberId === teamMemberId)
        .map((assignment) => assignment.clientId.trim())
        .filter(Boolean),
    ),
  );
